"""PyInstaller ve doğrudan çalıştırma için giriş betiği: python run.py"""
import sys

from sentinel.main import main

if __name__ == "__main__":
    sys.exit(main())
