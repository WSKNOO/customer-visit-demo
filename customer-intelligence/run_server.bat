@echo off
REM ============================================================
REM AI4Search MCP Server Launcher for Windows
REM ============================================================
title AI4Search MCP Server

call C:\Users\PC\miniconda3\Scripts\activate.bat tf2torch
cd /d %~dp0

echo [AI4Search MCP] Starting MCP server...
echo [AI4Search MCP] CWD: %CD%
echo [AI4Search MCP] Engine: stdio transport
echo.

mcp run search_mcp/server.py:mcp
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Server exited with code %ERRORLEVEL%
    pause
)
