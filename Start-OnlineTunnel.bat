@echo off
setlocal
title Ngrok Online Public Tunnel

echo ==========================================================
echo       Setting up Ngrok with your Authtoken...
echo ==========================================================
echo.

ngrok config add-authtoken 3Kdi4OFXTbqX95oXZVqBETA6eOX_2RqM8DwV3ChkX1qzVZz4K

echo.
echo ==========================================================
echo       Starting Public Tunnel on port 5000...
echo ==========================================================
echo.
echo Copy the "Forwarding" URL displayed below to access online!
echo.

ngrok http 5000

pause
