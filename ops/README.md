# Feelcoin Website Operations

This directory contains the runtime files used to generate the public
Feelcoin network-status endpoint.

## Files

- `feelcoin-network-status.py`
  Generates `/var/www/feelcoin.online/network-status.json`
  from the local Feelcoin daemon RPC.

- `feelcoin-network-status.service`
  systemd oneshot service.

- `feelcoin-network-status.timer`
  Runs the status generator every 30 seconds.

## Install

```bash
sudo cp ops/feelcoin-network-status.py /usr/local/bin/
sudo chmod 755 /usr/local/bin/feelcoin-network-status.py

sudo cp ops/feelcoin-network-status.service /etc/systemd/system/
sudo cp ops/feelcoin-network-status.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now feelcoin-network-status.timer

```
