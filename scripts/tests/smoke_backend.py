#!/usr/bin/env python3
"""Deterministic generic CLI backend target for smoke tests."""

import sys

_ = sys.argv[1:]  # prompt may be passed as trailing args
print("SMOKE BACKEND OK")
