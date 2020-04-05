#!/usr/bin/env python3
import cansh
import binascii
from intelhex import IntelHex
from tqdm import tqdm

ENABLE_TX_ADDR = 1634
ENABLE_RX_ADDR = 1635
COMMAND_TX_ADDR = 1636
COMMAND_RX_ADDR = 1637

START_ADDR = 0
END_ADDR = 1024*1024
CHUNK_SIZE = 0x1000

panda, bus = cansh.init(0, 500)
cansh.enable(panda, bus, ENABLE_TX_ADDR, ENABLE_RX_ADDR)
cansh.activate(panda, bus, COMMAND_TX_ADDR, COMMAND_RX_ADDR, silent=True)

ih = IntelHex()
try:
  for i in tqdm(range(START_ADDR, END_ADDR, CHUNK_SIZE)):
    cansh.cmd_send(panda, f'rd {i} {CHUNK_SIZE}', bus, COMMAND_TX_ADDR)
    lines = cansh.cmd_recv(panda, bus, COMMAND_RX_ADDR, silent=True)
    dat = b''
    for line in lines.replace(b'\r\n', b'\n').replace(b'\r', b'\n').split(b'\n'):
      if line and line[0:2] == b'0x':
        s = line.rstrip().split(b'  ', 1)
        assert len(s) == 2 or len(s) == 1 and s[0] == b'0x00000000', f'unexpected text: {s}'
        if len(s) == 2:
          dat += binascii.a2b_hex(s[1].replace(b' ', b''))
    ih[i:i+len(dat)] = list(dat)
finally:
  ih.write_hex_file('./dump.hex')
