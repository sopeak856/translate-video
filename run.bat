@echo off
chcp 65001 >nul
title Khmer Story Studio AI - Video Translator & Dubber

echo ======================================================================
echo    Khmer Story Studio AI - កម្មវិធីបកប្រែ និងបញ្ចូលសំឡេងរឿងជាភាសាខ្មែរ
echo ======================================================================
echo.
echo កំពុងចាប់ផ្តើមដំណើរការកម្មវិធី សូមរង់ចាំបន្តិច...
echo.

python -X utf8 main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] មានបញ្ហាក្នុងការបើកកម្មវិធី។
    pause
)
