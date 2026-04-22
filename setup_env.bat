@echo off
chcp 65001 >nul
echo ==========================================
echo 通勤研究项目 - 环境设置脚本
echo ==========================================
echo.

echo 检查Python版本...
python --version
echo.

echo 尝试安装依赖包...
echo 这可能需要几分钟时间...
echo.

REM 尝试使用ensurepip安装pip
python -m ensurepip --upgrade 2>nul

REM 安装依赖
python -m pip install numpy pandas geopandas shapely pyproj matplotlib scipy --quiet

echo.
echo 验证安装...
python -c "import numpy; import pandas; import geopandas; print('所有依赖包安装成功!')"

echo.
echo ==========================================
echo 环境设置完成
echo ==========================================
pause
