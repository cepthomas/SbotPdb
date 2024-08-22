# SbotPdb

This is a wrapper to allow a tcp client to run pdb remotely.
There are predecessors like this but SbotPdb has some tweaks to make it friendlier to
Sublime Text plugin debugging.

It's mostly hacked from [remote-db](https://github.com/ionelmc/python-remote-pdb)
with some bits of rpdb.py and pdbx.py.

Built for ST4 on Windows and Linux.

## Features

- Full pdb cli via your tty of choice. Or use SbotPdbClient.
- Optional colorizing of output.
- Timeout to unblock the plugin aka unfreeze ST.
- See [test](https://github.com/cepthomas/SbotPdb/blob/main/test_sbot_pdb.py) for an example.
  It's mostly just plain pdb.

## Settings

| Setting        | Description                              | Options                     |
| :--------      | :-------                                 | :------                     |
| host           | TCP host - usually localhost             | default="127.0.0.1"         |
| port           | TCP port in the range 49152 to 65535     | default=59120               |
| timeout        | Client connect after set_trace() called  | seconds 0=forever           |
| use_ansi_color | Server provides ansi color               |                             |
| debug          | SPrint debug statements to console       | true/false                  |


## SbotPdbClient

Optionally you can use the slightly-smarter SbotPdbClient tool.

- Reads the same settings file as the debugger.
- Pings the server and auto-connects when the breakpoint is hit. Reduces client/server synchronizing.
- Has some internal commands:
  - x exits the client, also stops the debugger.
  - hh shows an abbreviated help.


## Notes

Because of the nature of remote debugging, issuing a q(uit) command instead of c(ont) causes
an unhandled exception. This is also caused by closing the SbotPdbClient if you are using it.
[See](https://stackoverflow.com/a/34936583).
It is harmless but if it annoys you, add (or edit) this code somewhere in your plugins:

```python
import bdb
def _notify_exception(type, value, tb):
    if issubclass(type, bdb.BdbQuit):
        sys.__excepthook__(type, value, traceback)
        return
# Connect the last chance hook.
sys.excepthook = _notify_exception
```
