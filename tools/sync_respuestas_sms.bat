@echo off
REM Carga programada de respuestas SMS (Mowa -> CobAuto.dbo.CRM_SMS_*).
REM Lanzador opcional para configurar una tarea cuando el CRM se mueva de equipo.
cd /d "%~dp0.."
if not exist logs mkdir logs
python tools\sync_respuestas_sms.py >> logs\sync_respuestas_sms.log 2>&1
