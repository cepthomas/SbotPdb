# SbotPdb

This is a wrapper to allow a telnet client to run pdb remotely.
There are predecessors like this but SbotPdb has some tweaks to make it friendlier to
Sublime Text plugin debugging.

It's mostly hacked from [remote-db](https://github.com/ionelmc/python-remote-pdb)
with some bits of rpdb.py and pdbx.py.

Built for ST4 on Windows and Linux.

## Features

- Full pdb cli.
- Optional colorizing of output.
- Timeout to unblock the plugin aka unfreeze ST.
- See [test](https://github.com/cepthomas/SbotPdb/blob/main/test_sbot_pdb.py) for example.
  It's mostly just plain pdb.

## Settings

| Setting        | Description                              | Options                     |
| :--------      | :-------                                 | :------                     |
| host           | TCP host - usually localhost             | default="127.0.0.1"         |
| port           | TCP port in the range 49152 to 65535     | default=59120               |
| timeout        | Client connect after set_trace() called  | seconds 0=forever           |
| use_ansi_color | Server provides ansi color               |                             |
| debug          | SPrint debug statements to console       | true/false                  |


## Notes

- Because of the nature of remote debugging, issuing a q(uit) command instead of c(ont) causes
  an unhandled exception. This is harmless but could probably get a band-aid some time.
  [SO](https://stackoverflow.com/a/34936583).
- The first command received from client is garbage. It's a mystery.  
