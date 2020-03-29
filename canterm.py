#!/usr/bin/env python3
import os
from time import time, sleep
import struct

try:
  from prompt_toolkit import PromptSession
  from prompt_toolkit.history import FileHistory
except ModuleNotFoundError:
  # fallback to input()
  pass
from panda import Panda

CAN_SPEED_KBPS = int(os.getenv('CAN_SPEED_KBPS', 500))
DEBUG = os.getenv('DEBUG', False)

ENABLE_TX_ADDR = 0x75A
ENABLE_RX_ADDR = 0x75B
DISABLE_MSG = b'\x41\x00\x06\x00\x00\x00\x00\x00'
TERM_TX_ADDR=0x72A
TERM_RX_ADDR=0x72B
ACTIVATE_MSG = '\x01\x02\x03'
DEACTIVATE_MSG = '\x01\x02\x10'

ENABLE_MSGS = [
  b'\x41\x00\xA5\x00\xAF\xFE\xDE\xAD',
  b'\x41\x00\xA5\x00',
  b'\x41\x00\xA5\x00',
  b'\x41\x00\x00\x00\xAF\xFE\xDE\xAD',
]

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

def enable(panda, bus, retry):
  print("retry " if retry else "enable", end=' ')
  panda.can_clear(bus) # flush TX
  panda.can_clear(0xFFFF) # flush RX
  keys = None
  for i, msg in enumerate(ENABLE_MSGS):
    if len(msg) < 8 and keys and keys[i]:
      msg += keys[i]
    panda.can_send(ENABLE_TX_ADDR, msg, bus)
    if DEBUG: print(f'\n<-- TX: 0x{msg.hex()}')
    print(".", end='', flush=True)

    start = time()
    resp = None
    while not resp:
      msgs = panda.can_recv()
      for addr, t, dat, src in msgs:
        if bus != src or ENABLE_RX_ADDR != addr:
          continue
        if DEBUG: print(f'\n--> RX: 0x{dat.hex()}')
        print(".", end='', flush=True)
        if not keys:
          keys = get_keys(dat[4:8])
        resp = dat
      if not resp and len(msgs) == 0:
        sleep(0.1)
      if time() - start > 2:
        print("")
        return False

  print("")
  return True

def cmd_send(panda, cmd, bus):
  done = cmd.lower() == 'exit'
  if done:
    cmd = DEACTIVATE_MSG
  cmd = cmd.encode('latin-1') + b'\r'
  panda.can_clear(bus) # flush TX
  panda.can_clear(0xFFFF) # flush RX
  for i in range(0, len(cmd), 8):
    dat = cmd[i:i+8].ljust(8, b'\x00')
    if DEBUG: print(f'<-- TX: 0x{dat.hex()}')
    panda.can_send(TERM_TX_ADDR, dat, bus)
    sleep(0.1)
  return done

def cmd_recv(panda, bus):
  result = b''
  while True:
    msgs = panda.can_recv()
    for addr, t, dat, src in msgs:
      if bus != src or TERM_RX_ADDR != addr:
        continue
      if DEBUG: print(f'\n--> RX: 0x{dat.hex()}')
      txt = dat.replace(b'\r', b'\r\n').rstrip(b'\x00').decode('latin-1')
      result += dat.rstrip(b'\x00')
      print(txt, end='')
      if any(ss in result for ss in [b'\rOK\r', b'\nOK\n', b'Unbekanntes Kommando\r']):
        print('', end='', flush=True)
        return
    if len(msgs) == 0:
      sleep(0.1)

def main():
  panda = Panda()
  bus = 1 if panda.has_obd() else 0
  panda.set_can_speed_kbps(bus, CAN_SPEED_KBPS)
  panda.set_safety_mode(Panda.SAFETY_ALLOUTPUT)

  for i in range(10):
    # enable activating the terminal
    if enable(panda, bus, i != 0):
      break
    sleep(1)
  else:
    raise Exception('failed to enable!')

  try:
    os.system('clear')
    try:
      history = FileHistory(os.path.expanduser('~/.canterm_history'))
      session = PromptSession(history=history)
      prompt = session.prompt
    except NameError:
      print("================================")
      print("USING PYTHON INPUT PROMPT !!!")
      print("for a much better experience:")
      print("pip install prompt_toolkit")
      print("================================")
      print("")
      prompt = input

    # activate the terminal
    cmd_send(panda, ACTIVATE_MSG, bus)
    cmd_recv(panda, bus)

    while True:
      cmd = prompt('> ')
      done = cmd_send(panda, cmd, bus)
      if done: return
      cmd_recv(panda, bus)
  finally:
    # disable activating the terminal
    if DEBUG: print(f'<-- TX: 0x{DISABLE_MSG.hex()}')
    panda.can_send(ENABLE_TX_ADDR, DISABLE_MSG, bus)

if __name__ == "__main__":
  main()
