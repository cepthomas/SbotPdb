# Plugin Pdb

Sublime Text plugin for debugging ST plugins using pdb remotely over a tcp
connection. There are other remote pdb projects but this specifically targets
plugin debugging.

There's a fair amount hacked from [remote-db](https://github.com/ionelmc/python-remote-pdb)
with the addition of ST plugin hooks.

Built for ST4 on Windows and Linux.

## Features

- Use generic tcp client - linux terminal, windows putty, etc.
- Option for colorizing of output.
- Optional timeout can be set to force socket closure which unfreezes the ST application rather
  than having to forcibly shut it down.
- Work flow is to set a hard breakpoint using `sbot_pdb.set_trace()`, run the plugin,
  and then connect to it with your client. You can then execute pdb commands.

See [example](https://github.com/cepthomas/SbotPdb/blob/main/test_sbot_pdb.py).

![Plugin Pdb](cli1.png)


## ClientTool

Optionally you can use the slightly-smarter ClientTool tool which does all of the above plus:
- Reads the same settings file as Plugin Pdb so no fiddling with hosts.
- ClientTool automatically connects to the server. This means that you can edit/run your plugin code
  without having to restart the client.
- ClientTool detects dead server by requiring a response for each command sent.
- Provides some extra information, indicated by `!`.
- Has some extra commands:
  - `x` exits the client, also stops the server/debugger.
  - `hh` shows an abbreviated help.

ClientTool is Windows only but probably could work on linux.
Currently you need to build this yourself using VS 2022. Pull the source from
https://github.com/cepthomas/SbotPdb/tree/main/ClientTool, build, run.


![ClientTool](cli2.png)

## Settings

| Setting        | Description                              | Options                     |
| :--------      | :-------                                 | :------                     |
| host           | TCP host - usually localhost             | default="127.0.0.1"         |
| port           | TCP port in the range 49152 to 65535     | default=59120               |
| timeout        | Client connect after set_trace() called  | seconds 0=forever           |
| use_ansi_color | Server provides ansi color               |                             |

## Notes

Because of the nature of remote debugging, issuing a `q(uit)` command instead of `c(ont)` causes
an unhandled exception. This is also caused by closing the ClientTool if you are using it.
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
