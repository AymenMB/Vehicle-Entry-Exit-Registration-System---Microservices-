@echo off
REM Batch file wrapper to run plate detection client with the correct environment

REM Activate the virtual environment
call "%~dp0\aiplate_env\Scripts\activate.bat"

REM Run the Python script with all arguments passed to this batch file
python "%~dp0\plate_detection_client.py" %*

REM Deactivate the environment when done
call deactivate
