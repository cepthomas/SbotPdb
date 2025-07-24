# Plugin Pdb

Sublime Text plugin for debugging ST plugins using pdb remotely over a tcp
connection. There are other remote pdb projects but this specifically supports
plugin debugging.

There's a fair amount hacked from [remote-db](https://github.com/ionelmc/python-remote-pdb)
with the addition of ST plugin hooks.

Built for ST4 on Windows. Linux and OSX should be ok but are minimally tested - PRs welcome.

## Features

- Uses generic tcp client - linux terminal, windows putty, etc. Or better yet, use the
  [Fancy Client](#fancy-client).
- Option for colorizing of output. Totally unnecessary but cute.
- Optional timeout can be set to force socket closure which unfreezes the ST application rather
  than having to forcibly shut it down.

![Plugin Pdb](cli1.png)

## Usage

General workflow goes something like the following. A typical usage is demonstrated with
[example](https://github.com/cepthomas/SbotPdb/blob/main/example.py).

1. Copy `sbot_pdb.py` to the directory of the plugin you are debugging.

1. Optionally edit the configuration block in this file.

1. Edit the file being debugged and add this at the place you want to break:

  `from . import sbot_pdb; sbot_pdb.breakpoint()`

1. Run your client of choice.

1. Run the plugin being debugged. Client should break at the breakpoint line.

1. Now you can use any of the standard pdb commands.

It's usually handy to add a command like this in one of your menus:
```json
{ "caption": "Run pdb example", "command": "sbot_pdb_example" },
```
and a corresponding handler:
```python
class SbotPdbExampleCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        from . import sbot_pdb; sbot_pdb.breakpoint()
        my_plugin_code()
```

## Fancy Client

Optionally you can use the smarter `sbot_pdb_client.py` script which does all of the above plus:
- Automatically connects to the server. This means that you can edit/run your plugin code
  without having to restart the client.
- Detects unresponsive server by requiring a response for each command sent.
- Provides some extra system status information, indicated by `!` (or marker of your choosing).
- Workflow is similar to the above except you can now reload/run the plugin code as part of your dev/edit cycle.
- Optionally edit the configuration block in this file.
- Use ctrl-C to exit the client. The plugin will also stop/unblock.

![Fancy Client](cli2.png)

## Notes

A `sublime-settings` file doesn't make sense for this plugin. Settings are hard-coded in the py files
  themselves. This seems ok since they are unlikely to change often.

Because of the nature of remote debugging, issuing a `q(uit)` command instead of `c(ont)` causes
  an unhandled `BdbQuit` [exception](https://stackoverflow.com/a/34936583).
  Similarly, unhandled `ConnectionError` can occur. They are harmless but if it annoys you,
  add (or edit) this code somewhere in your plugins:
```python
import bdb
def excepthook(type, value, tb):
    if issubclass(type, bdb.BdbQuit) or issubclass(type, ConnectionError):
        return  # ignore
    sys.__excepthook__(type, value, traceback)

# Connect the last chance hook.
sys.excepthook = excepthook
```

Note that sublime is blocked while running the debugger so you can't edit files using ST.
  You may have to resort to *another editor!*.
