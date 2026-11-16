import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from game import lan, perfil  # noqa: E402


class TestLan(unittest.TestCase):
    def test_ip_permitido(self):
        for ip in ("192.168.0.5", "10.1.2.3", "172.16.0.9", "127.0.0.1"):
            self.assertTrue(lan.ip_permitido(ip), ip)
        for ip in ("8.8.8.8", "1.1.1.1", "lixo", ""):
            self.assertFalse(lan.ip_permitido(ip), ip)

    def test_limpar_perfil_descarta_campos_extras(self):
        p = lan.limpar_perfil({"id": "RN-ABC12345", "nick": "Ana", "pais": "BR", "hack": "x", "descricao": "oi"})
        self.assertIsNotNone(p)
        self.assertNotIn("hack", p)
        self.assertNotIn("descricao", p)
        self.assertIsNone(lan.limpar_perfil("texto"))
        self.assertIsNone(lan.limpar_perfil({"nick": "sem id"}))

    def test_perfil_criada(self):
        arq = Path(tempfile.mkdtemp()) / "perfil.json"
        self.assertFalse(perfil.ler(arq)["criada"])
        perfil.salvar(arq, {"nick": "Ana", "pais": "BR", "criada": True})
        self.assertTrue(perfil.ler(arq)["criada"])


if __name__ == "__main__":
    unittest.main()
