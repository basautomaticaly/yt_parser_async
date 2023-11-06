@echo off
echo Updating Python...
python -m pip install --upgrade pip
echo Installing/Updating required libraries...
python -m pip install --upgrade google-auth google-auth-httplib2 google-auth-oauthlib google-api-python-client oauthlib
echo Update completed successfully
pause
