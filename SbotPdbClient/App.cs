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
        NetworkStream? _stream = null;
        TcpClient? _client = null;
        readonly string _eol = "\r\n";
        readonly ConcurrentQueue<string> _cmdQ = new();
        #endregion

        /// <summary>
        /// Run the loop.
        /// </summary>
        public void Go()
        {
            try
            {
                bool run = true;

                // Run user cli input in a thread.
                Task.Run(() => {
                    while (run)
                    {
                        _cmdQ.Enqueue(Console.ReadLine()!);
                    }
                });

                // Echo anything from server to user.
                if (_client?.Available > 0)
                {
                    var data = new byte[_client.Available];
                    _stream?.Read(data, 0, data.Length);
                    string s = Encoding.ASCII.GetString(data, 0, data.Length);
                    Console.Write(s);
                }

                // Process any user commands.
                while (run)
                {
                    if (_cmdQ.TryDequeue(out var cliInput))
                    {
                        switch (cliInput)
                        {
                            case "x":
                                run = false;
                                break;
                            case "":
                                // idle
                                break;
                            case "col":
                                DoColorTest();
                                break;
                            case "cfg":
                                GetConfig();
                                break;
                            default:
                                // Send any other user input to server.
                                Debug.WriteLine("Got " + cliInput);
                                byte[] data = Encoding.ASCII.GetBytes(cliInput + _eol);
                                _stream?.Write(data, 0, data.Length);
                                break;
                        }
                    }

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

            // Connect.
            var ipEndPoint = new IPEndPoint(IPAddress.Parse(_host), _port);
            _client = new TcpClient(AddressFamily.InterNetwork);
            _client.Connect(ipEndPoint);
            _stream = _client.GetStream();
            _stream.ReadTimeout = 100; // poll
        }

        /// <summary>
        /// Hand parse config files. Json parser is too heavy for this app.
        /// </summary>
        /// <exception cref="ArgumentException"></exception>
        public void GetConfig()
        {
            // Overlay default and user options.
            var cfg1 = Environment.ExpandEnvironmentVariables(@"%APPDATA%\Sublime Text\Packages\SbotPdb\SbotPdb.sublime-settings");
            Parse(cfg1);
            var cfg2 = Environment.ExpandEnvironmentVariables(@"%APPDATA%\Sublime Text\Packages\User\SbotPdb.sublime-settings");
            Parse(cfg2);

            void Parse(string fn)
            {
                foreach (string l in File.ReadAllLines(fn))
                {
                    var s = l.Trim();

                    if (!s.StartsWith("\""))
                    {
                        continue;
                    }
                    s = s.Replace("\"", "").Replace(",", "");

                    var parts = s.Split(new string[] { ":" }, StringSplitOptions.TrimEntries);
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
                            throw new ArgumentException(name);
                    }
                }
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
        /// Resource management.
        /// </summary>
        public void Dispose()
        {
            _stream?.Dispose();
            _stream = null;
            _client?.Dispose();
            _client = null;
        }
    }
}
