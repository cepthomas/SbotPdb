using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.IO;
using System.Linq;
using System.Diagnostics;
using System.Threading.Tasks;
using System.Collections.Concurrent;


namespace ClientTool
{
    internal class App : IDisposable
    {
        #region Server config
        string _host = "???";
        int _port = 0;
        #endregion

        #region Fields
        TcpClient? _client = null;
        readonly string _eol = "\r\n";
        readonly ConcurrentQueue<string?> _cmdQ = new();

        // Human polling time in msec.
        const int LOOP_TIME = 100;

        // Server must reply to commands in msec.
        const int SERVER_LOSS_TIME = 100;

        readonly Stopwatch _watch = new();
        long _sendts = 0;
        #endregion

        /// <summary>
        /// Run the loop.
        /// </summary>
        public void Go()
        {
            try
            {
                Console.Title = "Plugin Pdb ClientTool";
                Console.BufferHeight = 300;
                Console.BufferWidth = 120;

                _watch.Start();

                GetConfig();

                Console.WriteLine($"! Plugin Pdb ClientTool started on {_host}:{_port}");
                Console.WriteLine($"! Run your plugin code to debug");

                bool run = true;

                // Run user cli input in a thread.
                Task.Run(() => { while (run) { _cmdQ.Enqueue(Console.ReadLine()); } });

                // Main/forever loop.
                while (run)
                {
                    ///// Try re/connecting?
                    if (_client is null)
                    {
                        Reset();
                        var ipEndPoint = new IPEndPoint(IPAddress.Parse(_host), _port);
                        _client = new TcpClient(AddressFamily.InterNetwork);

                        try
                        {
                            _client.Connect(ipEndPoint);
                        }
                        catch (SocketException e)
                        {
                            // Ignore and retry later.
                            // Maybe should check code. https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-error-codes-2
                            Reset();
                        }
                        catch (Exception e)
                        {
                            // Other errors are considered fatal.
                            Console.WriteLine($"! Fatal error:{e}");
                            Reset();
                            run = false;
                        }
                    }

                    ///// Check for loss of server.
                    if (_sendts > 0)
                    {
                        var dur = _watch.ElapsedMilliseconds - _sendts;
                        if (dur - LOOP_TIME > SERVER_LOSS_TIME)
                        {
                            Console.WriteLine("! Server stopped");
                            Reset();
                        }
                    }

                    ///// Echo anything from server to user.
                    if (_client is not null && _client.Available > 0)
                    {
                        var data = new byte[_client.Available];
                        _client.GetStream().Read(data, 0, data.Length);
                        string s = Encoding.ASCII.GetString(data, 0, data.Length);
                        DoTrace($"INN:{s}");
                        _sendts = 0; // reset watchdog
                        var rtdur = _watch.ElapsedMilliseconds - _sendts;
                        Console.Write($"{s}");
                    }

                    ///// Check for user input.
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
                                    DoTrace($"OUT:{cliInput}");
                                    // Measure round trip.
                                    _sendts = _watch.ElapsedMilliseconds;
                                    byte[] data = Encoding.ASCII.GetBytes(cliInput + _eol);
                                    _client.GetStream().Write(data, 0, data.Length);
                                    _client.GetStream().Flush();
                                }
                                else
                                {
                                    Console.WriteLine("! Can't execute - not connected");
                                    _sendts = 0;
                                }
                                break;
                        }
                    }

                    ///// Human time.
                    System.Threading.Thread.Sleep(LOOP_TIME);
                }
            }
            catch (Exception e)
            {
                // Errors are considered fatal.
                Console.WriteLine($"1 Fatal error:{e}");
            }
            finally
            {
                _watch.Stop();
                Reset();
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
                            //case "timeout":
                            //    _timeout = int.Parse(val);
                            //    break;
                            //case "use_ansi_color":
                            //    _useAnsiColor = bool.Parse(val);
                            //    break;
                            default:
                                //throw new ArgumentException(s);
                                break;
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
            Console.WriteLine("! Succinct help");

            string[] lines =
            [
                "h(elp)         [command]",
                "hh                                           What you see now.",
                "q(uit)                                       Don't do this.",
                "x(it)                                        Do this.",
                "run or restart [args ...]                    Restart the program with 'args'.",
                "s(tep)                                       Step into function.",
                "n(ext)                                       Step over function.",
                "r(eturn)                                     Step out of function.",
                "c(ont(inue))                                 Continue execution until breakpoint.",
                "unt(il)        [lineno]                      Continue until 'lineno' or next.",
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
            string NL = Environment.NewLine; // shortcut
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
        /// Diagnostics.
        /// </summary>
        /// <param name="msg"></param>
        void DoTrace(string msg)
        {
            //msg = msg.Replace("\n", "_N").Replace("\r", "_R");
            //File.AppendAllText(@"some.txt", msg + Environment.NewLine);
        }

        /// <summary>
        /// Reset comms.
        /// </summary>
        public void Reset()
        {
            _client?.Dispose();
            _client = null;
            // Reset watchdog.
            _sendts = 0;
        }

        /// <summary>
        /// Resource management.
        /// </summary>
        public void Dispose()
        {
            _client?.Dispose();
            _client = null;
        }
    }
}
