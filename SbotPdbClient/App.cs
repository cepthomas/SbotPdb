using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.IO;
using System.Linq;
using System.Diagnostics;
using System.Threading.Tasks;
using System.Collections.Concurrent;


namespace SbotPdbClient
{
    internal class App : IDisposable
    {
        #region Server config
        string _host = "???";
        int _port = 0;
        int _timeout = 5; // server listen timeout
        bool _useAnsiColor = true;
        bool _debug = true;
        #endregion

        #region Fields
        TcpClient? _client = null;
        readonly string _eol = "\r\n";
        readonly ConcurrentQueue<string?> _cmdQ = new();
        #endregion

        /// <summary>
        /// Run the loop.
        /// </summary>
        public void Go()
        {
            try
            {
                GetConfig();

                Console.WriteLine($"SbotPdbClient on {_host}:{_port}");
                Console.WriteLine($"Start your plugin code to debug");

                bool run = true;

                // Run user cli input in a thread.
                Task.Run(() => { while (run) { _cmdQ.Enqueue(Console.ReadLine()); } });

                // Main/forever loop.
                while (run)
                {
                    // Try reconnecting? // TODO1 doesn't detect that server has exited debugger. Maybe reopen every time?
                    if (_client is null)
                    {
                        Connect();
                    }

                    // Echo anything from server to user.
                    if (_client is not null && _client.Available > 0)
                    {
                        var data = new byte[_client.Available];
                        _client.GetStream().Read(data, 0, data.Length);
                        string s = Encoding.ASCII.GetString(data, 0, data.Length);
                        Console.Write(s);
                    }

                    // Check for user input.
                    if (_cmdQ.TryDequeue(out var cliInput))
                    {
                        switch (cliInput)
                        {
                            case null: // should never happen
                                break;
                            case "x": // internal - exit client
                                run = false;
                                break;
                            case "hh": // internal - short usage
                                ShortUsage();
                                break;
                            default: // Send any other user input to server.
                                if (_client is not null)
                                {
                                    byte[] data = Encoding.ASCII.GetBytes(cliInput + _eol);
                                    _client.GetStream().Write(data, 0, data.Length);
                                }
                                else
                                {
                                    Console.Write("Can't execute - not connected");
                                }
                                break;
                        }
                    }

                    // Human time.
                    System.Threading.Thread.Sleep(100);
                }
            }
            catch (Exception e)
            {
                Console.Write(e.ToString());
            }
        }

        /// <summary>
        /// Say hello to server.
        /// </summary>
        public void Connect()
        {
            Dispose();

            // Try to connect.
            var ipEndPoint = new IPEndPoint(IPAddress.Parse(_host), _port);
            _client = new TcpClient(AddressFamily.InterNetwork);

            try
            {
                _client.Connect(ipEndPoint);
            }
            catch (SocketException e)
            {
                if (e.SocketErrorCode > 0)
                {
                    // Ignore and retry later. Could do smarter processing of errors?
                    //https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-error-codes-2
                }
                _client.Dispose();
                _client = null;
            }
            catch (Exception e)
            {
                // Other errors are considered fatal.
                Console.Write(e.ToString());
                _client.Dispose();
                _client = null;
            }
        }

        /// <summary>
        /// Hand parse config files. Json parser is too heavy for this app.
        /// </summary>
        /// <exception cref="ArgumentException"></exception>
        public void GetConfig()
        {
            // Overlay default and user options.
            var pkgspath = Path.Join(Environment.ExpandEnvironmentVariables(@"%APPDATA%"), "Sublime Text", "Packages");
            Parse(Path.Join(pkgspath, "SbotPdb", "SbotPdb.sublime-settings"), true);
            Parse(Path.Join(pkgspath, "User", "SbotPdb.sublime-settings"), false);

            void Parse(string fn, bool required)
            {
                if (!required && !Path.Exists(fn))
                {
                    return;
                }

                foreach (string l in File.ReadAllLines(fn))
                {
                    var s = l.Trim();

                    if (s.StartsWith('\"'))
                    {
                        s = s.Replace("\"", "").Replace(",", "");

                        var parts = s.Split([":"], StringSplitOptions.TrimEntries);
                        var name = parts[0];
                        var val = parts[1].Trim();

                        switch (name)
                        {
                            case "host":
                                _host = val;
                                break;
                            case "port":
                                _port = int.Parse(val);
                                break;
                            case "timeout":
                                _timeout = int.Parse(val);
                                break;
                            case "use_ansi_color":
                                _useAnsiColor = bool.Parse(val);
                                break;
                            case "debug":
                                _debug = bool.Parse(val);
                                break;
                            default:
                                throw new ArgumentException(s);
                        }
                    }
                }
            }
        }

        /// <summary>
        /// Succinct usage.
        /// </summary>
        public void ShortUsage()
        {
            string[] lines =
            [
                "h(elp)         [command]",
                "q(uit)",
                "run or restart [args ...]                    Restart the program with 'args'.",
                "s(tep)                                       Step into function.",
                "n(ext)                                       Step over function.",
                "unt(il)        [lineno]                      Continue until 'lineno' or next.",
                "r(eturn)                                     Step out of function.",
                "c(ont(inue))                                 Continue execution until breakpoint.",
                "j(ump)         lineno                        Jump to 'lineno'.",
                "w(here)                                      Print a stack trace. '>' is current frame.",
                "d(own)         [count]                       Move the current frame 'count' or 1 levels down/newer.",
                "u(p)           [count]                       Move the current frame 'count' or 1 levels up/older.",
                "b(reak)        [([fn:]line or func) [,cond]] Set break point with optional bool condition. If no args, display all breakpoints.",
                "tbreak         same as b                     Temporary breakpoint.",
                "cl(ear)        [filename:lineno or bpnumber] Clear breakpoint. Def is all with conf.",
                "l(ist)         [first[, last]]               Source code for the current file. Current is '->'. Exception line is '>>'.",
                "ll or longlist                               List all source code for the current function or frame.",
                "a(rgs)                                       Print the args of the current function.",
                "retval                                       Print the return value for the current function.",
                "p              expression                    Evaluate 'expression' in the current context.",
                "pp             expression                    Like p except pretty-printed.",
                "!              statement                     Execute one-line statement in the context of the current stack frame. Also handles 'global varname;'.",
                "display        [expression]                  When exec stops, display the value of 'expression' or all if it changed. Note mutables may fool you.",
                "undisplay      [expression]                  Do not display 'expression' or all anymore.",
            ];

            foreach (string line in lines)
            {
                Console.WriteLine(line);
            }
        }

        /// <summary>
        /// Test stuff.
        /// </summary>
        public void DoColorTest()
        {
            //string NL = Environment.NewLine; // shortcut
            string NORMAL = "\x1b[39m";
            string RED = "\x1b[91m";
            string GREEN = "\x1b[92m";
            string YELLOW = "\x1b[93m";
            string BLUE = "\x1b[94m";
            string MAGENTA = "\x1b[95m";
            string CYAN = "\x1b[96m";
            string GREY = "\x1b[97m";
            string BOLD = "\x1b[1m";
            string NOBOLD = "\x1b[22m";
            string UNDERLINE = "\x1b[4m";
            string NOUNDERLINE = "\x1b[24m";
            string REVERSE = "\x1b[7m";
            string NOREVERSE = "\x1b[27m";

            Console.WriteLine($"This is {RED}Red{NORMAL}, {GREEN}Green{NORMAL}, {YELLOW}Yellow{NORMAL}, {BLUE}Blue{NORMAL}, {MAGENTA}Magenta{NORMAL}, {CYAN}Cyan{NORMAL}, {GREY}Grey{NORMAL}! ");
            Console.WriteLine($"This is {BOLD}Bold{NOBOLD}, {UNDERLINE}Underline{NOUNDERLINE}, {REVERSE}Reverse{NOREVERSE}! ");
        }

        /// <summary>
        /// Resource management.
        /// </summary>
        public void Dispose()
        {
            // _stream?.Dispose();
            // _stream = null;
            _client?.Dispose();
            _client = null;
        }
    }
}
