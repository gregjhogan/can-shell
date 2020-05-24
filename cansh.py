#!/usr/bin/env python3
import os
import sys
from time import time, sleep
import struct
import argparse
import contextlib
import io

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from panda import Panda

ENABLE_TX_ADDR = int(os.getenv('CANTERM_ENABLE_TX_ADDR', 0))
ENABLE_RX_ADDR = int(os.getenv('CANTERM_ENABLE_RX_ADDR', 0))
COMMAND_TX_ADDR = int(os.getenv('CANTERM_COMMAND_TX_ADDR', 0))
COMMAND_RX_ADDR = int(os.getenv('CANTERM_COMMAND_RX_ADDR', 0))
FACTORY_MODE_BYPASS = int(os.getenv('CANTERM_FACTORY_MODE_BYPASS', 0))
CAN_BUS = int(os.getenv('CANTERM_BUS', 0))
SPEED_KBPS = int(os.getenv('CANTERM_SPEED_KBPS', 0))

ECHO = int(os.getenv('CANTERM_ECHO', 0))
DEBUG = int(os.getenv('CANTERM_DEBUG', 0))
STOP_ON_ERROR = int(os.getenv('CANTERM_STOP_ON_ERROR', 0))

ADDR_SEARCH_RANGE = range(0x600, 0x800)

ENABLE_MSGS = [
  b'\x41\x00\xA5\x00\xAF\xFE\xDE\xAD',
  b'\x41\x00\xA5\x00',
  b'\x41\x00\xA5\x00',
  b'\x41\x00\x00\x00\xAF\xFE\xDE\xAD',
]
DISABLE_MSG = b'\x41\x00\x06\x00\x00\x00\x00\x00'

FACTORY_MODE_MSGS = [
  b'\x41\x00\x05\x00\x00\x00\x00\x00', # enable
  b'\x41\x00\x06\x00\x00\x00\x00\x00', # disable
]

ACTIVATE_MSG = '\x01\x02\x03'
DEACTIVATE_MSG = '\x01\x02\x10'

def get_keys(code):
  s1, _ = struct.unpack(">HH", code)
  k1 = (s1 * s1 + 0x9176) & 0xFFFF
  k2 = k1 ^ 0x9176
  return [
    None,
    struct.pack(">HH", k1, s1),
    struct.pack(">HH", k1, k2),
    None,
  ]

def find_enable_addrs(panda, bus, addr_range):
  msg = ENABLE_MSGS[0]
  for tx_addr in addr_range:
    panda.can_clear(bus) # flush TX
    panda.can_clear(0xFFFF) # flush RX
    if DEBUG: print(f'\n<-- TX {hex(tx_addr)}: 0x{msg.hex()}')
    panda.can_send(tx_addr, msg, bus)
    print('.', end='', flush=True)
    start_time = time()
    while time() - start_time < 0.1:
      msgs = panda.can_recv()
      for rx_addr, t, dat, src in msgs:
        if bus != src or dat[0] != msg[0] or dat[2] != msg[2]:
          continue
        if DEBUG: print(f'\n--> RX {hex(rx_addr)}: 0x{dat.hex()}')
        return tx_addr, rx_addr
  return None, None

def find_command_addrs(panda, bus, addr_range, addr_skips):
  addr_range = [addr for addr in addr_range if addr not in addr_skips]

  msg = (ACTIVATE_MSG + '\r').encode().ljust(8, b'\x00')
  panda.can_clear(bus) # flush TX
  panda.can_clear(0xFFFF) # flush RX
  # activate terminal
  panda.can_send_many([(tx_addr, None, msg, bus) for tx_addr in addr_range])
  if DEBUG: print(f'\n<-- TX MANY: 0x{msg.hex()}')
  # wait for 'whoami` output to finish sending
  sleep(1)

  msg = b'help\r'.ljust(8, b'\x00')
  for tx_addr in addr_range:
    panda.can_clear(bus) # flush TX
    panda.can_clear(0xFFFF) # flush RX
    panda.can_send(tx_addr, msg, bus)
    if DEBUG: print(f'\n<-- TX {hex(tx_addr)}: 0x{msg.hex()}')
    print('.', end='', flush=True)
    start_time = time()
    while time() - start_time < 0.1:
      msgs = panda.can_recv()
      for rx_addr, t, dat, src in msgs:
        if bus != src or b'Daimler' not in dat:
          continue
        if DEBUG: print(f'\n--> RX {hex(rx_addr)}: 0x{dat.hex()}')
        return tx_addr, rx_addr
  return None, None

def find_addrs(panda, bus):
  enable_tx_addr = None
  enable_rx_addr = None
  print("[SCAN FOR TX/RX ENABLE ADDRESS]")
  print(f"scanning address range {hex(ADDR_SEARCH_RANGE[0])}-{hex(ADDR_SEARCH_RANGE[-1])} ", end="")
  enable_tx_addr, enable_rx_addr = find_enable_addrs(panda, bus, ADDR_SEARCH_RANGE)
  print("")
  if enable_tx_addr is not None and enable_rx_addr is not None:
    print("enable addrs found!")
    print(f"CANTERM_ENABLE_TX_ADDR={enable_tx_addr}")
    print(f"CANTERM_ENABLE_RX_ADDR={enable_rx_addr}")
  else:
    print("unable to find enable addresses")
    print("(cycle ecu power and try again)")
    return

  print("\n[ENABLE CAN TERMINAL]")
  print("wait ", end="")
  for i in range(5):
    sleep(1)
    print(".", end="", flush=True)
  print("")
  enable(panda, bus, enable_tx_addr, enable_rx_addr)

  command_tx_addr = None
  command_rx_addr = None
  print("\n[SCAN FOR TX/RX COMMAND ADDRESS]")
  print(f"scanning address range {hex(ADDR_SEARCH_RANGE[0])}-{hex(ADDR_SEARCH_RANGE[-1])} ", end="")
  command_tx_addr, command_rx_addr = find_command_addrs(panda, bus, ADDR_SEARCH_RANGE, [enable_tx_addr, enable_rx_addr])
  print("")
  if command_tx_addr is not None and command_rx_addr is not None:
    print("enable addrs found!")
    print(f"CANTERM_COMMAND_TX_ADDR={command_tx_addr}")
    print(f"CANTERM_COMMAND_RX_ADDR={command_rx_addr}")
  else:
    print("unable to find command addresses")
    print("(cycle ecu power and try again)")
    return

def enable(panda, bus, tx_addr, rx_addr, silent=False, timeout=1):
  if DEBUG: print("--- ENABLE")
  if not silent: print("enable", end=' ')
  panda.can_clear(bus) # flush TX
  panda.can_clear(0xFFFF) # flush RX
  keys = None
  for i, msg in enumerate(ENABLE_MSGS):
    if len(msg) < 8 and keys and keys[i]:
      msg += keys[i]
    if DEBUG: print(f'{"" if silent else os.linesep}<-- TX {hex(tx_addr)}: 0x{msg.hex()}')
    panda.can_send(tx_addr, msg, bus)
    if not silent: print(".", end='', flush=True)

    start = time()
    resp = None
    while not resp:
      msgs = panda.can_recv()
      for addr, t, dat, src in msgs:
        if bus != src or rx_addr != addr:
          continue
        if DEBUG: print(f'{"" if silent else os.linesep}--> RX {hex(rx_addr)}: 0x{dat.hex()}')
        if not silent: print(".", end='', flush=True)
        if not keys:
          keys = get_keys(dat[4:8])
        resp = dat
      if not resp and len(msgs) == 0:
        sleep(0.1)
      if time() - start > timeout:
        if not silent: print("")
        raise TimeoutError("failed to enable!")

  if not silent: print("")

def factory_mode_bypass(panda, bus, tx_addr, rx_addr, silent=False, timeout=1):
  if DEBUG: print("--- FACTORY MODE BYPASS")
  if not silent: print("bypass", end=' ')
  panda.can_clear(bus) # flush TX
  panda.can_clear(0xFFFF) # flush RX
  for i, msg in enumerate(FACTORY_MODE_MSGS):
    if DEBUG: print(f'{"" if silent else os.linesep}<-- TX {hex(tx_addr)}: 0x{msg.hex()}')
    panda.can_send(tx_addr, msg, bus)
    if not silent: print(".", end='', flush=True)

    start = time()
    resp = None
    while not resp:
      msgs = panda.can_recv()
      for addr, t, dat, src in msgs:
        if bus != src or rx_addr != addr:
          continue
        if DEBUG: print(f'{"" if silent else os.linesep}--> RX {hex(rx_addr)}: 0x{dat.hex()}')
        if not silent: print(".", end='', flush=True)
        resp = dat
      if not resp and len(msgs) == 0:
        sleep(0.1)
      if time() - start > timeout:
        if not silent: print("")
        raise TimeoutError("failed to bypass factory mode!")

  if not silent: print("")

def disable(panda, bus, tx_addr):
  if DEBUG: print("--- DISABLE")
  msg = DISABLE_MSG
  panda.can_clear(bus) # flush TX
  panda.can_clear(0xFFFF) # flush RX
  if DEBUG: print(f'<-- TX {hex(tx_addr)}: 0x{msg.hex()}')
  panda.can_send(tx_addr, msg, bus)

def activate(panda, bus, tx_addr, rx_addr):
  if DEBUG: print("--- ACTIVATE")
  cmd_send(panda, ACTIVATE_MSG, bus, tx_addr)
  return cmd_recv(panda, bus, rx_addr)

def deactivate(panda, bus, tx_addr):
  if DEBUG: print("--- DEACTIVATE")
  cmd_send(panda, DEACTIVATE_MSG, bus, tx_addr)
  # there is no response

def cmd_send(panda, cmd, bus, tx_addr):
  # exit command is fake
  if cmd.lower() == 'exit':
    return True
  cmd = cmd.encode('latin-1') + b'\r'
  panda.can_clear(bus) # flush TX
  panda.can_clear(0xFFFF) # flush RX
  for i in range(0, len(cmd), 8):
    dat = cmd[i:i+8].ljust(8, b'\x00')
    if DEBUG: print(f'<-- TX {hex(tx_addr)}: 0x{dat.hex()}')
    panda.can_send(tx_addr, dat, bus)
    # send too fast and the ECU skips messages
    sleep(0.1)
  return False

def normalize_output(output):
  return output.rstrip(b'\x00').replace(b'\r\n', b'\n').replace(b'\r', b'\n')

def decode_output(lines, stop_on_error, charset='latin-1'):
  retcode = None
  text = list()
  for line in lines:
    if line == b'OK':
      retcode = 0
    elif line == b'Unbekanntes Kommando':
      retcode = 1
      if not stop_on_error:
        text.append("invalid command - type 'help' for valid commands")
    elif len(line) > 0:
      text.append(line.decode(charset))
  return text, retcode

def parse_output(output, stop_on_error):
  output = normalize_output(output)
  lines = output.split(b'\n')
  partial = lines[-1]
  text, retcode = decode_output(lines[:-1], stop_on_error)
  return partial, text, retcode

def cmd_recv(panda, bus, rx_addr, stop_on_error=False, timeout=5):
  start = time()
  partial_output = b''
  while True:
    msgs = panda.can_recv()
    for addr, t, dat, src in msgs:
      if bus != src or rx_addr != addr:
        continue
      start = time()
      if DEBUG: print(f'--> RX {hex(rx_addr)}: 0x{dat.hex()}')
      partial_output += dat
      partial_output, text, retcode = parse_output(partial_output, stop_on_error)
      for line in text:
        yield line
      if retcode is not None:
        if retcode and stop_on_error:
          raise Exception("command failed!")
        return

    if len(msgs) == 0:
      sleep(0.1)
    if time() - start > timeout:
      raise TimeoutError("failed to receive!")

def init(bus, speed_kbps, silent=False):
  f = io.StringIO()
  with contextlib.redirect_stdout(f):
    panda = Panda()
  if DEBUG or not silent: print(f.getvalue())
  if bus == -1:
    bus = 1 if panda.has_obd() else 0
  if DEBUG: print(f'--- BUS: {bus}')
  if speed_kbps:
    if DEBUG: print(f'--- SPEED: {speed_kbps} kbps')
    panda.set_can_speed_kbps(bus, speed_kbps)
  panda.set_safety_mode(Panda.SAFETY_ALLOUTPUT)
  return panda, bus

def interactive(tx_addr, rx_addr):
  history = FileHistory(os.path.expanduser('~/.cansh_history'))
  session = PromptSession(message='> ', history=history)

  while True:
    cmd = session.prompt()
    if (ECHO or DEBUG): print(f"--- {cmd}")
    done = cmd_send(panda, cmd, bus, tx_addr)
    if done: return
    for line in cmd_recv(panda, bus, rx_addr):
      print(line)
    sys.stdout.flush()

def non_interactive(source, tx_addr, rx_addr, stop_on_error):
    for line in source:
      if line.startswith('#!'):
        continue
      cmd = line.rstrip(' \t\r\n')
      if not cmd:
        continue
      if (ECHO or DEBUG): print(f"--- {cmd}")
      cmd_send(panda, cmd, bus, tx_addr)
      for line in cmd_recv(panda, bus, rx_addr, stop_on_error=stop_on_error):
        print(line)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('file', nargs='?', type=argparse.FileType('r'), default=sys.stdin, help='script to run')
  parser.add_argument('-e', action='store_true', help='stop on first error')
  parser.add_argument('-c', metavar='COMMAND', type=str, help='single command to run (then exit)')
  parser.add_argument('-x', action='store_true', help='echo commands executed')
  parser.add_argument('-b', metavar='BUS', type=int, default=-1, help='CAN bus to use')
  parser.add_argument('-v', action='store_true', help='verbose output')
  parser.add_argument('--enable-tx-addr', type=int, default=0, help='enable TX address')
  parser.add_argument('--enable-rx-addr', type=int, default=0, help='enable RX address')
  parser.add_argument('--command-tx-addr', type=int, default=0, help='command TX address')
  parser.add_argument('--command-rx-addr', type=int, default=0, help='command RX address')
  parser.add_argument('--factory-mode-bypass', action='store_true', help='enable then disable factory mode to activate')
  parser.add_argument('--can-speed', type=int, default=0, help='CAN bus speed in Kbps')
  parser.add_argument('--scan', action='store_true', help='scan for can terminal TX/RX addresses')
  args = parser.parse_args()
  is_tty = sys.stdin.isatty() and not args.c and args.file.name == '<stdin>'
  if not STOP_ON_ERROR: STOP_ON_ERROR = args.e
  if not ECHO: ECHO = args.x
  if not DEBUG: DEBUG = args.v
  if not SPEED_KBPS: SPEED_KBPS = args.can_speed
  if not CAN_BUS: CAN_BUS = args.b
  if not ENABLE_TX_ADDR: ENABLE_TX_ADDR = args.enable_tx_addr
  if not ENABLE_RX_ADDR: ENABLE_RX_ADDR = args.enable_rx_addr
  if not COMMAND_TX_ADDR: COMMAND_TX_ADDR = args.command_tx_addr
  if not COMMAND_RX_ADDR: COMMAND_RX_ADDR = args.command_rx_addr
  if not FACTORY_MODE_BYPASS: FACTORY_MODE_BYPASS = args.factory_mode_bypass

  if not args.scan and (not ENABLE_TX_ADDR or not ENABLE_RX_ADDR or not COMMAND_TX_ADDR or not COMMAND_RX_ADDR):
    print("You must specify all of the following: ENABLE_TX_ADDR, ENABLE_RX_ADDR, COMMAND_TX_ADDR, COMMAND_RX_ADDR", file=sys.stderr)
    sys.exit(1)

  panda, bus = init(CAN_BUS, SPEED_KBPS, silent=not is_tty)
  if args.scan:
    find_addrs(panda, bus)
    sys.exit(0)

  enable(panda, bus, ENABLE_TX_ADDR, ENABLE_RX_ADDR, silent=not is_tty)
  if FACTORY_MODE_BYPASS:
    factory_mode_bypass(panda, bus, ENABLE_TX_ADDR, ENABLE_RX_ADDR, silent=not is_tty)
  for line in activate(panda, bus, COMMAND_TX_ADDR, COMMAND_RX_ADDR):
    if is_tty:
      print(line)
  sys.stdout.flush()

  try:
    if is_tty:
      interactive(COMMAND_TX_ADDR, COMMAND_RX_ADDR)
    else:
      source = [args.c] if args.c else args.file
      non_interactive(source, COMMAND_TX_ADDR, COMMAND_RX_ADDR, STOP_ON_ERROR)
  finally:
    deactivate(panda, COMMAND_TX_ADDR, bus)
