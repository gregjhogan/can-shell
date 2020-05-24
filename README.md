# CAN shell
command processor for automotive ECUs with a built-in text-based CAN bus terminal (using a [panda](https://comma.ai/shop/products/panda-obd-ii-dongle))

[![CAN terminal](https://img.youtube.com/vi/Ouie8a050hs/0.jpg)](https://www.youtube.com/watch?v=Ouie8a050hs)

## Usage
note that most vehicles with a gateway block the required addresses, so you need a direct communication line for any of this to work

### hardware
Currently supported:
* [comma.ai panda](https://comma.ai/shop/products/panda-obd-ii-dongle)

Honda Accord 2018+ EPS connector:
* [TE 1-967616-1](https://www.te.com/usa-en/product-1-967616-1.html)

Tesla AP1 EPAS connector:
* [TE 1-967616-1](https://www.te.com/usa-en/product-1-967616-1.html)

### setup
```sh
pip install -r requirements.txt
sudo ln -s $(pwd)/cansh /usr/local/bin/
```

### scan for TX/RX addresses (if you don't already know them)
```sh
cansh --scan
```

### setup address environment variables
Honda Accord 2018+ EPS
```sh
export CANTERM_ENABLE_TX_ADDR=1882
export CANTERM_ENABLE_RX_ADDR=1883
export CANTERM_COMMAND_TX_ADDR=1834
export CANTERM_COMMAND_RX_ADDR=1835
```
Tesla AP1 EPAS
```sh
export CANTERM_ENABLE_TX_ADDR=1634
export CANTERM_ENABLE_RX_ADDR=1635
export CANTERM_COMMAND_TX_ADDR=1636
export CANTERM_COMMAND_RX_ADDR=1637
export CANTERM_FACTORY_MODE_BYPASS=1
```

### interactive shell
```sh
# assumes environment variables are set up
cansh
# type 'help' to see available commands and 'exit' to quit
```
or (without environment variables)
```sh
# insert appropriate address (decimal) before running below commands
cansh --enable-tx-addr <enable-tx-addr> --enable-rx-addr <enable-rx-addr> --command-tx-addr <command-tx-addr> --command-rx-addr <command-rx-addr>
# type 'help' to see available commands and 'exit' to quit
```

### single command
```sh
# assumes environment variables are set up
cansh -c 'rd 0x00000000 1'
```

### non-interactive (pipe)
```sh
# assumes environment variables are set up
echo 'rd 0x00000000 1' | cansh
```

### execute script [example.sh](example.sh) (multi-command)
```sh
# assumes environment variables are set up
./example.sh
```
or
```sh
# assumes environment variables are set up
cansh ./example.sh
```

## Enhancements
* additional ECUs with a CAN terminal most likely exist, write support and submit a PR!
* a good shell supports variables, conditional branch logic and looping constructs
* additional hardware support
