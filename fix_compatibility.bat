@echo off
echo Fixing SQLAlchemy compatibility issue...
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Uninstall incompatible version and install compatible one
echo Uninstalling SQLAlchemy 2.0.23...
pip uninstall -y SQLAlchemy

echo Installing compatible SQLAlchemy 1.4.53...
pip install SQLAlchemy==1.4.53

echo.
echo Compatibility fix completed!
echo.
echo The ultra-fast pyodbc method should work regardless of SQLAlchemy
echo Your uploads should still be much faster than before
echo.
echo Press any key to continue...
pause > nul
