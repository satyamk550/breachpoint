[CmdletBinding()]
param(
    [string]$BaseUrl
)

if (-not $BaseUrl) {
    if ($env:EVENT_BASE_URL) {
        $BaseUrl = $env:EVENT_BASE_URL
    } else {
        $HttpPort = if ($env:HTTP_PORT) { $env:HTTP_PORT } else { "8080" }
        $BaseUrl = "http://localhost:$HttpPort/api/v1"
    }
}

$BaseUrl = $BaseUrl.TrimEnd('/')
$AdminUsername = Read-Host "Admin username"
$SecurePassword = Read-Host "Admin password" -AsSecureString
if (-not $AdminUsername -or -not $SecurePassword) {
    throw "Admin credentials are required."
}
$Credential = [pscredential]::new($AdminUsername, $SecurePassword)

# Cookies are retained only in memory for this process. Nothing is written to disk.
$script:Cookies = @{}
$script:Session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

function Get-CookieHeader {
    ($script:Cookies.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "; "
}

function Save-ResponseCookies {
    param([object]$Response)

    if (-not $Response.Headers["Set-Cookie"]) { return }
    foreach ($SetCookie in @($Response.Headers["Set-Cookie"])) {
        $Match = [regex]::Match($SetCookie, "(?<name>[^=;]+)=(?<value>[^;]*)")
        if ($Match.Success) {
            $Name = $Match.Groups["name"].Value
            $Value = $Match.Groups["value"].Value
            $script:Cookies[$Name] = $Value
            $Cookie = New-Object System.Net.Cookie($Name, $Value, "/", "localhost")
            $Cookie.Secure = $false
            $script:Session.Cookies.Add($Cookie)
        }
    }
}

function Invoke-EventApi {
    param(
        [Parameter(Mandatory)] [ValidateSet("GET", "POST", "PUT")] [string]$Method,
        [Parameter(Mandatory)] [string]$Path,
        [object]$Body
    )

    $Headers = @{ Accept = "application/json" }
    $CookieHeader = Get-CookieHeader
    if ($CookieHeader) { $Headers["Cookie"] = $CookieHeader }

    if ($Method -ne "GET") {
        if (-not $script:Cookies.ContainsKey("csrf_token")) {
            Invoke-EventApi -Method GET -Path "/event/status" | Out-Null
        }
        if (-not $script:Cookies.ContainsKey("csrf_token")) {
            throw "The event server did not issue a CSRF cookie."
        }
        $Headers["X-CSRF-Token"] = $script:Cookies["csrf_token"]
        $CookieHeader = Get-CookieHeader
        if ($CookieHeader) { $Headers["Cookie"] = $CookieHeader }
        Write-Verbose "Sending $Method $Path with cookies: $($script:Cookies.Keys -join ', ')"
    }

    $RequestParams = @{
        Uri = "$BaseUrl$Path"
        Method = $Method
        Headers = $Headers
        WebSession = $script:Session
        UseBasicParsing = $true
    }
    if ($null -ne $Body) {
        $RequestParams["ContentType"] = "application/json"
        $RequestParams["Body"] = ($Body | ConvertTo-Json -Compress)
    }

    try {
        $Response = Invoke-WebRequest @RequestParams
        Save-ResponseCookies -Response $Response
        if ($Response.Content) {
            return ($Response.Content | ConvertFrom-Json)
        }
        return $null
    } catch {
        $ErrorResponse = $_.Exception.Response
        if ($ErrorResponse) {
            $Reader = New-Object System.IO.StreamReader($ErrorResponse.GetResponseStream())
            $ErrorBody = $Reader.ReadToEnd()
            $Reader.Dispose()
            throw "HTTP $([int]$ErrorResponse.StatusCode): $ErrorBody"
        }
        throw
    }
}

# Prime the double-submit CSRF cookie, then authenticate using the in-memory cookie jar.
Invoke-EventApi -Method GET -Path "/event/status" | Out-Null
$Login = Invoke-EventApi -Method POST -Path "/auth/login" -Body @{
    username = $Credential.UserName
    password = $Credential.GetNetworkCredential().Password
}
if (-not $Login) { throw "Admin login returned no response." }

Write-Host "Connected to $BaseUrl as $($Credential.UserName). Password retained only in memory."

do {
    $Command = (Read-Host "Command [status/start/pause/resume/end/set-times/quit]").Trim().ToLowerInvariant()
    try {
        switch ($Command) {
            "status" {
                Invoke-EventApi -Method GET -Path "/event/status" | ConvertTo-Json -Depth 10
            }
            "start" {
                Invoke-EventApi -Method POST -Path "/event/admin/start" | ConvertTo-Json -Depth 10
            }
            "pause" {
                Invoke-EventApi -Method POST -Path "/event/admin/pause" | ConvertTo-Json -Depth 10
            }
            "resume" {
                Invoke-EventApi -Method POST -Path "/event/admin/resume" | ConvertTo-Json -Depth 10
            }
            "end" {
                Invoke-EventApi -Method POST -Path "/event/admin/end" | ConvertTo-Json -Depth 10
            }
            "set-times" {
                $Start = Read-Host "Start ISO UTC (blank for null)"
                $End = Read-Host "End ISO UTC (blank for null)"
                Invoke-EventApi -Method PUT -Path "/event/admin/times" -Body @{
                    start = if ($Start) { $Start } else { $null }
                    end = if ($End) { $End } else { $null }
                } | ConvertTo-Json -Depth 10
            }
            "quit" { }
            "" { }
            default { Write-Host "Unknown command." }
        }
    } catch {
        Write-Error $_
    }
} while ($Command -ne "quit")
