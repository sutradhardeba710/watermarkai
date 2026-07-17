"""Task modules — wired up incrementally across phases 3/5/6/7.

Phase 1 registers the modules so celery -A workers.celery_app worker starts;
the actual task functions are filled in their respective phases.
"""
