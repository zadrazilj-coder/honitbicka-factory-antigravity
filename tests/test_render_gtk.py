"""Testy detekce GTK DLL adresáře na Windows (honbicka.sazba.render).

Kořenová příčina bugu: Python 3.8+ na Windows ignoruje PATH pro závislosti DLL
(„safe DLL search") — nutné `os.add_dll_directory()`. Testy ověřují logiku
výběru kandidáta bez závislosti na tom, jestli GTK v CI/testovacím prostředí
skutečně je.
"""

from __future__ import annotations

import os

import pytest

from honbicka.sazba import render


@pytest.fixture(autouse=True)
def _reset_pripojeno(monkeypatch):
    """Každý test začíná s „nepřipojeno" a nešpiní ostatní testy/moduly."""
    monkeypatch.setattr(render, "_gtk_dll_pripojeno", False)
    yield


def _fake_gtk_dir(tmp_path):
    d = tmp_path / "fake_gtk"
    d.mkdir()
    (d / render._GTK_ZNACKOVA_DLL).write_bytes(b"")
    return str(d)


def test_najde_platny_kandidat(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "add_dll_directory", lambda p: None, raising=False)
    gtk_dir = _fake_gtk_dir(tmp_path)
    vysledek = render._zajisti_gtk_dll_cestu([gtk_dir])
    assert vysledek == gtk_dir
    assert render._gtk_dll_pripojeno is True


def test_preskoci_neexistujici_a_najde_platny(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "add_dll_directory", lambda p: None, raising=False)
    gtk_dir = _fake_gtk_dir(tmp_path)
    vysledek = render._zajisti_gtk_dll_cestu(
        [str(tmp_path / "neexistuje"), "", gtk_dir]
    )
    assert vysledek == gtk_dir


def test_zadny_kandidat_nenajde_nic(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "add_dll_directory", lambda p: None, raising=False)
    vysledek = render._zajisti_gtk_dll_cestu([str(tmp_path / "neexistuje")])
    assert vysledek is None
    assert render._gtk_dll_pripojeno is False


def test_idempotentni_podruhe_neudela_nic(tmp_path, monkeypatch):
    volani = []
    monkeypatch.setattr(os, "add_dll_directory", lambda p: volani.append(p), raising=False)
    gtk_dir = _fake_gtk_dir(tmp_path)
    render._zajisti_gtk_dll_cestu([gtk_dir])
    render._zajisti_gtk_dll_cestu([gtk_dir])  # už připojeno → no-op
    assert len(volani) == 1


def test_mimo_windows_je_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(render.sys, "platform", "linux")
    monkeypatch.setattr(os, "add_dll_directory", lambda p: None, raising=False)
    gtk_dir = _fake_gtk_dir(tmp_path)
    vysledek = render._zajisti_gtk_dll_cestu([gtk_dir])
    assert vysledek is None
    assert render._gtk_dll_pripojeno is False


def test_bez_add_dll_directory_je_noop(tmp_path, monkeypatch):
    monkeypatch.delattr(os, "add_dll_directory", raising=False)
    gtk_dir = _fake_gtk_dir(tmp_path)
    vysledek = render._zajisti_gtk_dll_cestu([gtk_dir])
    assert vysledek is None


def test_env_var_je_prvni_kandidat(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "add_dll_directory", lambda p: None, raising=False)
    gtk_dir = _fake_gtk_dir(tmp_path)
    monkeypatch.setenv("HONBICKA_GTK_DIR", gtk_dir)
    # výchozí seznam (bez explicitních kandidátů) musí env var respektovat
    import importlib
    importlib.reload(render)
    monkeypatch.setattr(render, "_gtk_dll_pripojeno", False)
    monkeypatch.setattr(os, "add_dll_directory", lambda p: None, raising=False)
    vysledek = render._zajisti_gtk_dll_cestu()
    assert vysledek == gtk_dir
    importlib.reload(render)  # ať test neovlivní zbytek běhu
