#!/usr/bin/env python3
import cansh
import argparse
import binascii
from intelhex import IntelHex
from tqdm import tqdm

ENABLE_TX_ADDR = 1634
ENABLE_RX_ADDR = 1635
COMMAND_TX_ADDR = 1636
COMMAND_RX_ADDR = 1637

START_ADDR = 0x0
END_ADDR = 0xFFFFF
CHUNK_SIZE = 0xFF0

parser = argparse.ArgumentParser()
parser.add_argument('file', metavar='output-file-name', nargs=1, help='name of output file')
args = parser.parse_args()

panda, bus = cansh.init(bus=0, speed_kbps=500)
cansh.enable(panda, bus, ENABLE_TX_ADDR, ENABLE_RX_ADDR)
for line in cansh.activate(panda, bus, COMMAND_TX_ADDR, COMMAND_RX_ADDR):
  pass # ignore output

print('dumping ...')
pbar = tqdm(total=END_ADDR-START_ADDR)
ih = IntelHex()
try:
  for i in range(START_ADDR, END_ADDR+1, CHUNK_SIZE):
    cansh.cmd_send(panda, f'rd {i} {CHUNK_SIZE}', bus, COMMAND_TX_ADDR)
    dat = b''
    for line in cansh.cmd_recv(panda, bus, COMMAND_RX_ADDR, stop_on_error=True):
      if line and line[0:2] == '0x':
        s = line.rstrip().split('  ', 1)
        assert len(s) == 2 or len(s) == 1 and s[0] == '0x00000000', f'unexpected text: {s}'
        if len(s) == 2:
          chunk = binascii.a2b_hex(s[1].replace(' ', ''))
          dat += chunk
          pbar.update(len(chunk))
    ih[i:i+len(dat)] = list(dat)
finally:
  ih.write_hex_file(args.file[0])
