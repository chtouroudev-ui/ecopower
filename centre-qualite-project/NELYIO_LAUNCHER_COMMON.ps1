# Nelyio V59 production launcher helpers - Windows PowerShell 5.1 compatible.
# Shared helpers only. Dot-sourcing this file does NOT start any service.

function ConvertTo-NelyioProcessArgument {
    param([AllowEmptyString()][string]$Value)
    if ($null -eq $Value -or $Value.Length -eq 0) { return '""' }
    if ($Value -notmatch '[\s"]') { return $Value }
    # Windows command-line quoting: escape quotes and trailing backslashes.
    $escaped = [regex]::Replace($Value, '(\\*)"', '${1}${1}\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '${1}${1}')
    return '"' + $escaped + '"'
}

function Get-NelyioPowerShell {
    $exe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw 'Windows PowerShell est introuvable.'
    }
    return $exe
}

function Invoke-NelyioChildProcess {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [string[]]$ProcessArguments = @(),
        [Parameter(Mandatory=$true)][string]$WorkingDirectory,
        [Parameter(Mandatory=$true)][string]$LogPrefix,
        [ValidateRange(1,600)][int]$TimeoutSeconds = 120
    )
    $outFile = $LogPrefix + '_stdout.log'
    $errFile = $LogPrefix + '_stderr.log'
    $folder = Split-Path -Parent $outFile
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $commandLine = (($ProcessArguments | ForEach-Object { ConvertTo-NelyioProcessArgument $_ }) -join ' ')
    $options = @{
        FilePath = $Executable
        WorkingDirectory = $WorkingDirectory
        PassThru = $true
        WindowStyle = 'Hidden'
        RedirectStandardOutput = $outFile
        RedirectStandardError = $errFile
        ErrorAction = 'Stop'
    }
    if ($commandLine) { $options.ArgumentList = $commandLine }
    # Never use Start-Process -Wait here: it waits for the whole process tree.
    # Python and Caddy must remain alive AFTER their short launcher exits.
    $child = Start-Process @options
    try {
        $null = $child.Handle
        $finished = $child.WaitForExit($TimeoutSeconds * 1000)
        if (-not $finished) {
            # Only the launcher just created is stopped, NOT its descendants.
            # Already running services and unrelated applications are untouched.
            try { $child.Kill() } catch {}
            return [pscustomobject]@{ ExitCode=124; TimedOut=$true; StdoutPath=$outFile; StderrPath=$errFile; Pid=$child.Id }
        }
        $child.Refresh()
        $exitCode = $child.ExitCode
        if ($null -eq $exitCode) { throw 'Code retour du processus indisponible.' }
        return [pscustomobject]@{ ExitCode=[int]$exitCode; TimedOut=$false; StdoutPath=$outFile; StderrPath=$errFile; Pid=$child.Id }
    } finally {
        $child.Dispose()
    }
}

function Invoke-NelyioScript {
    param(
        [Parameter(Mandatory=$true)][string]$ScriptPath,
        [string[]]$ScriptArguments = @(),
        [Parameter(Mandatory=$true)][string]$WorkingDirectory,
        [Parameter(Mandatory=$true)][string]$LogPrefix,
        [ValidateRange(1,600)][int]$TimeoutSeconds = 120
    )
    if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) { throw "Script introuvable : $ScriptPath" }
    $arguments = @('-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$ScriptPath) + $ScriptArguments
    return Invoke-NelyioChildProcess -Executable (Get-NelyioPowerShell) -ProcessArguments $arguments -WorkingDirectory $WorkingDirectory -LogPrefix $LogPrefix -TimeoutSeconds $TimeoutSeconds
}

function Initialize-NelyioProbe {
    if ('NelyioHttpsHotfix.HttpProbe' -as [type]) { return }
    # A pure .NET per-request certificate callback avoids PowerShell runspace
    # callback issues and does NOT change global certificate-validation policy.
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
namespace NelyioHttpsHotfix {
    public sealed class ProbeReply {
        public int StatusCode;
        public string Body = "";
        public string Error = "";
    }
    public static class HttpProbe {
        public static ProbeReply Read(string address, int timeoutMs, bool diagnosticLocalTls) {
            ProbeReply result = new ProbeReply();
            try {
                Uri uri = new Uri(address);
                if (uri.Scheme != "http" && uri.Scheme != "https") throw new ArgumentException("Protocole invalide");
                if (diagnosticLocalTls && !uri.IsLoopback) throw new ArgumentException("TLS de diagnostic limite au loopback");
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create(uri);
                req.Proxy = null;
                req.AllowAutoRedirect = false;
                req.KeepAlive = false;
                req.Timeout = timeoutMs;
                req.ReadWriteTimeout = timeoutMs;
                req.UserAgent = "Nelyio-V59-Launcher";
                if (diagnosticLocalTls) {
                    req.ServerCertificateValidationCallback = delegate(object sender, X509Certificate cert, X509Chain chain, SslPolicyErrors errors) { return true; };
                }
                using (HttpWebResponse response = (HttpWebResponse)req.GetResponse()) {
                    result.StatusCode = (int)response.StatusCode;
                    using (StreamReader reader = new StreamReader(response.GetResponseStream())) {
                        char[] buffer = new char[16385];
                        int used = 0;
                        while (used < buffer.Length) {
                            int n = reader.Read(buffer, used, buffer.Length-used);
                            if (n == 0) break;
                            used += n;
                        }
                        if (used > 16384) throw new InvalidDataException("Reponse healthz trop volumineuse");
                        result.Body = new string(buffer,0,used);
                    }
                }
            } catch (WebException e) {
                result.Error = e.Message;
                if (e.Response != null) e.Response.Close();
            } catch (Exception e) { result.Error = e.Message; }
            return result;
        }
    }
}
'@ -Language CSharp -ErrorAction Stop
}

function Test-NelyioHealth {
    param([Parameter(Mandatory=$true)][string]$Url, [switch]$DiagnosticLocalTls, [int]$TimeoutMilliseconds=3000, [string]$ExpectedBuild="")
    Initialize-NelyioProbe
    $reply = [NelyioHttpsHotfix.HttpProbe]::Read($Url,$TimeoutMilliseconds,[bool]$DiagnosticLocalTls)
    if ($reply.StatusCode -ne 200 -or $reply.Error) { return $false }
    try {
        $body = $reply.Body | ConvertFrom-Json -ErrorAction Stop
        return ($body.ok -eq $true -and $body.service -eq 'nelyio-backend' -and ((-not $ExpectedBuild) -or $body.build -eq $ExpectedBuild))
    } catch { return $false }
}

function Test-NelyioPort {
    param([int]$Port)
    $client = New-Object Net.Sockets.TcpClient
    try {
        $attempt = $client.BeginConnect('127.0.0.1',$Port,$null,$null)
        if (-not $attempt.AsyncWaitHandle.WaitOne(700,$false)) { return $false }
        $client.EndConnect($attempt)
        return $true
    } catch { return $false } finally { $client.Close() }
}
