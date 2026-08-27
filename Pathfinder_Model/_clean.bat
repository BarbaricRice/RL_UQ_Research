@echo on

SET ROOT=%~dp0
SET ROOT=%ROOT:~0,-1%

SET PTH_ROOT=C:\Program Files\Pathfinder 2026

"%PTH_ROOT%\PathfinderConsole.exe" -W-MainClass=montecarlo/CleanResults Pathfinder_Model_simulations.json
