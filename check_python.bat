@echo off
echo Dang kiem tra Python tren may tinh cua ban...
where python >nul 2>nul
if %errorlevel%==0 (
    echo [OK] Tim thay Python tai:
    where python
) else (
    echo [!] Khong tim thay lenh 'python' trong PATH.
    echo Dang thu tim lenh 'py'...
    where py >nul 2>nul
    if %errorlevel%==0 (
        echo [OK] Tim thay lenh 'py'. Ban co the dung 'py update_content.py' thay cho 'python'.
    ) else (
        echo [!] Khong tim thay ca 'python' va 'py'. 
        echo Ban hay vao Microsoft Store tai 'Python 3.12' hoac tai tu python.org va nho tick vao 'Add Python to PATH'.
    )
)
pause
