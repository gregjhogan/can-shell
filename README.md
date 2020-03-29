# CAN shell
command processor for automotive ECUs with a built-in text-based CAN bus terminal (using a [panda](https://comma.ai/shop/products/panda-obd-ii-dongle))

[![CAN terminal](https://img.youtube.com/vi/Ouie8a050hs/0.jpg)](https://www.youtube.com/watch?v=Ouie8a050hs)

## Usage

### setup
```sh
pip install -r requirements.txt
sudo ln -s $(pwd)/cansh /usr/local/bin/
```

### interactive shell
```sh
cansh
```

### single command
```sh
cansh -c 'rd 0x00000000 1'
```

### non-interactive (pipe)
```sh
echo 'rd 0x00000000 1' | cansh
```

### execute script [example.sh](example.sh) (multi-command)
```sh
./example.sh
```
or
```sh
cansh ./example.sh
```

## Supported ECUs
* Honda
  * 2018+ Accord EPS
* Tesla
  * AP1 EPAS (coming soon)

## Contributing
additional ECUs with a CAN terminal most likely exist, write support and submit a PR!
