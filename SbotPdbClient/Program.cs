﻿
using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;

namespace SbotPdbClient
{
    internal class Program
    {
        static void Main(string[] args)
        {
            var app = new App();
            app.Go();
        }
    }
}
