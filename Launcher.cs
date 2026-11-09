using System;
using System.IO;
using System.Diagnostics;
using System.Threading;

namespace TCCCafeArara
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.Title = "Sistema de Maturacao Cafe Arara - TCC";
            Console.OutputEncoding = System.Text.Encoding.UTF8;

            PrintBanner();

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string venvDir = Path.Combine(baseDir, "venv");
            string venvPython = Path.Combine(venvDir, "Scripts", "python.exe");
            string venvStreamlit = Path.Combine(venvDir, "Scripts", "streamlit.exe");
            string reqFile = Path.Combine(baseDir, "requirements.txt");
            string appFile = Path.Combine(baseDir, "app", "app.py");

            // 1. Verificar / Localizar Python
            string pythonExe = FindPython(venvPython);

            if (string.IsNullOrEmpty(pythonExe))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("\n[ERRO CRITICO] O Python nao foi encontrado no seu computador!");
                Console.ResetColor();
                Console.WriteLine("Por favor, instale o Python 3.10+ em: https://www.python.org/downloads/");
                Console.WriteLine("Certifique-se de marcar a opcao 'Add Python to PATH' durante a instalacao.\n");
                Console.WriteLine("Pressione qualquer tecla para sair...");
                Console.ReadKey();
                return;
            }

            // 2. Criar ambiente virtual se nao existir
            if (!File.Exists(venvPython))
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("\n[1/3] Criando ambiente virtual isolado (venv)... Aguarde...");
                Console.ResetColor();

                int code = RunProcess(pythonExe, "-m venv venv", baseDir);
                if (code != 0 || !File.Exists(venvPython))
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("\n[ERRO] Falha ao criar ambiente virtual venv.");
                    Console.ResetColor();
                    Console.WriteLine("Pressione qualquer tecla para sair...");
                    Console.ReadKey();
                    return;
                }
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("[OK] Ambiente virtual criado com sucesso!");
                Console.ResetColor();
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("[1/3] Ambiente virtual (venv) verificado e pronto.");
                Console.ResetColor();
            }

            // 3. Verificar e Instalar Requisitos (requirements.txt)
            bool needsInstall = !File.Exists(venvStreamlit);
            if (args.Length > 0 && args[0].ToLower().Contains("update"))
            {
                needsInstall = true;
            }

            if (needsInstall)
            {
                Console.ForegroundColor = ConsoleColor.Cyan;
                Console.WriteLine("\n[2/3] Baixando e instalando todas as bibliotecas e requisitos...");
                Console.WriteLine("      (YOLOv8, Streamlit, OpenCV, Torch, etc. Isso pode levar alguns minutos)...\n");
                Console.ResetColor();

                RunProcess(venvPython, "-m pip install --upgrade pip", baseDir);
                int pipCode = RunProcess(venvPython, string.Format("-m pip install -r \"{0}\"", reqFile), baseDir);

                if (pipCode != 0)
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("\n[AVISO] Ocorreu uma falha ou aviso durante a instalacao dos requisitos.");
                    Console.ResetColor();
                }
                else
                {
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("\n[OK] Todos os requisitos foram baixados e instalados com sucesso!");
                    Console.ResetColor();
                }
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("[2/3] Requisitos e dependencias ja estao prontos para execucao.");
                Console.ResetColor();
            }

            // 4. Executar o Streamlit e abrir o Localhost
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("\n[3/3] Iniciando o servidor web da aplicacao...\n");
            Console.ResetColor();

            if (!File.Exists(appFile))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine(string.Format("[ERRO] Arquivo principal nao encontrado: {0}", appFile));
                Console.ResetColor();
                Console.WriteLine("Pressione qualquer tecla para sair...");
                Console.ReadKey();
                return;
            }

            // Thread para abrir o navegador apos o servidor iniciar
            Thread browserThread = new Thread(new ThreadStart(delegate()
            {
                Thread.Sleep(2500);
                try
                {
                    Process.Start("http://localhost:8501");
                }
                catch { }
            }));
            browserThread.IsBackground = true;
            browserThread.Start();

            PrintReadyBanner();

            // Executar o Streamlit repassando saidas ao terminal
            string streamlitExe = File.Exists(venvStreamlit) ? venvStreamlit : "streamlit";
            RunProcess(streamlitExe, string.Format("run \"{0}\" --server.port 8501", appFile), baseDir);
        }

        static void PrintBanner()
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("========================================================================");
            Console.WriteLine("   COFFEE ARARA - IDENTIFICACAO E MATURACAO AUTOMATICA (TCC)");
            Console.WriteLine("   Visao Computacional com Deep Learning (YOLOv8 + Streamlit)");
            Console.WriteLine("========================================================================");
            Console.ResetColor();
        }

        static void PrintReadyBanner()
        {
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("========================================================================");
            Console.WriteLine("   >> SERVIDOR LOCAL INICIADO COM SUCESSO! <<");
            Console.WriteLine("   Acesse no navegador: http://localhost:8501");
            Console.WriteLine("   (Uma aba do navegador sera aberta automaticamente em instantes)");
            Console.WriteLine("========================================================================");
            Console.WriteLine("   * Para encerrar a aplicacao: feche esta janela ou aperte Ctrl+C.");
            Console.WriteLine("========================================================================\n");
            Console.ResetColor();
        }

        static string FindPython(string preferredVenvPython)
        {
            if (File.Exists(preferredVenvPython))
            {
                return preferredVenvPython;
            }

            string[] candidatePaths = new string[]
            {
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python314", "python.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python312", "python.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python311", "python.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python310", "python.exe"),
                @"C:\Python312\python.exe",
                @"C:\Python311\python.exe",
                @"C:\Python310\python.exe"
            };

            foreach (string p in candidatePaths)
            {
                if (File.Exists(p)) return p;
            }

            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("python.exe", "--version");
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                using (Process p = Process.Start(psi))
                {
                    p.WaitForExit();
                    if (p.ExitCode == 0) return "python.exe";
                }
            }
            catch { }

            return null;
        }

        static int RunProcess(string fileName, string arguments, string workingDir)
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = fileName;
            psi.Arguments = arguments;
            psi.WorkingDirectory = workingDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = false;

            try
            {
                using (Process proc = Process.Start(psi))
                {
                    proc.WaitForExit();
                    return proc.ExitCode;
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine(string.Format("[FALHA] Nao foi possivel iniciar {0}: {1}", fileName, ex.Message));
                Console.ResetColor();
                return -1;
            }
        }
    }
}
