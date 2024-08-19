
using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;

namespace SbotPdbClient
{
    internal class App
    {
        public void Go()
        {
            Console.WriteLine("Hello, World!");

            DoColor();


            //https://learn.microsoft.com/en-us/dotnet/fundamentals/networking/sockets/tcp-classes#create-a-tcpclient

            var ipEndPoint = new IPEndPoint(IPAddress.Parse("127.0.0.1"), 4444);

            using var client = new TcpClient(AddressFamily.InterNetwork);

            client.Connect(ipEndPoint);


            using NetworkStream stream = client.GetStream();

            var buffer = new byte[1_024];
            int received = stream.Read(buffer);

            var message = Encoding.UTF8.GetString(buffer, 0, received);
            Console.WriteLine($"Message received: \"{message}\"");
            // Sample output:
            //     Message received: "📅 8/22/2022 9:07:17 AM 🕛"



        }


        public void DoColor()
        {
            string NL          = Environment.NewLine; // shortcut
            string NORMAL      =  "\x1b[39m";
            string RED         =  "\x1b[91m";
            string GREEN       =  "\x1b[92m";
            string YELLOW      =  "\x1b[93m";
            string BLUE        =  "\x1b[94m";
            string MAGENTA     =  "\x1b[95m";
            string CYAN        =  "\x1b[96m";
            string GREY        =  "\x1b[97m";
            string BOLD        =  "\x1b[1m";
            string NOBOLD      =  "\x1b[22m";
            string UNDERLINE   =  "\x1b[4m";
            string NOUNDERLINE =  "\x1b[24m";
            string REVERSE     =  "\x1b[7m";
            string NOREVERSE   =  "\x1b[27m";

            Console.WriteLine($"This is {RED}Red{NORMAL}, {GREEN}Green{NORMAL}, {YELLOW}Yellow{NORMAL}, {BLUE}Blue{NORMAL}, {MAGENTA}Magenta{NORMAL}, {CYAN}Cyan{NORMAL}, {GREY}Grey{NORMAL}! ");
            Console.WriteLine($"This is {BOLD}Bold{NOBOLD}, {UNDERLINE}Underline{NOUNDERLINE}, {REVERSE}Reverse{NOREVERSE}! ");
        }        


        //void other()
        //{
        //    int timeout = _dm.FEConfiguration.OASServerTimeout * 1000; // Convert to milliseconds
        //    int retries = _dm.FEConfiguration.OASServerRetries;

        //    if (!_shuttingDown)
        //    {
        //        using (_udpClient = new UdpClient(clientPort))
        //        {
        //            _udpClient.Client.SendTimeout = timeout;
        //            _udpClient.Client.ReceiveTimeout = timeout;

        //            try
        //            {
        //                // set the remote host
        //                IPAddress serverIp = IPAddress.Parse(_dm.FEConfiguration.OASServerIP);
        //                int serverPort = _dm.FEConfiguration.OASServerPort;
        //                _udpClient.Connect(serverIp, serverPort);

        //                _logger.Debug(
        //                    "SendingOASMessage {0} {1} Length({2}), " +
        //                    "serverIp({3}), " +
        //                    "serverPort({4}), clientPort({5}), , clientEndPoint({6}), " +
        //                    "TimeOut({7}), Retries({8})",
        //                    args.SendUdpHeader.MsgType, args.SendUdpHeader.SequenceNumber, args.Msg.Length,
        //                    _dm.FEConfiguration.OASServerIP,
        //                    _dm.FEConfiguration.OASServerPort, _dm.FEConfiguration.OASLocalPort, _udpClient.Client.LocalEndPoint,
        //                    timeout, retries);

        //                do
        //                {
        //                    _logger.Debug("SendingOASMessage {0} {1} msg({2})",
        //                        args.SendUdpHeader.MsgType, args.SendUdpHeader.SequenceNumber, args.Msg);

        //                    // Sends message to the host.
        //                    byte[] sendBytes = Encoding.ASCII.GetBytes(args.Msg);
        //                    _udpClient.Send(sendBytes, sendBytes.Length);

        //                    reply = UdpReceive(args);

        //                } while ((reply.StatusCode != StatusCode.Ok) && (retries-- > 0));
        //            }
        //            catch (Exception e)
        //            {
        //                reply.StatusCode = StatusCode.SendFail;
        //                _logger.ErrorException(string.Format("Exception parsing OAS Server IP ({0})",
        //                    _dm.FEConfiguration.OASServerIP), e);
        //            }
        //            _udpClient.Close(); // close the UDP connection
        //        } // using
        //        _udpClient = null; // Feed the garbage collector
        //    }
        //}

    }
}
