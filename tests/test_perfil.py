import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from game import perfil  # noqa: E402


class TestPerfil(unittest.TestCase):
    def setUp(self):
        self.arq = Path(tempfile.mkdtemp()) / "perfil.json"

    def test_cria_perfil_com_id_estavel(self):
        a = perfil.ler(self.arq)
        self.assertRegex(a["id"], r"^RN-[0-9A-F]{8}$")
        self.assertEqual(perfil.ler(self.arq)["id"], a["id"])

    def test_salvar_valida_e_mantem_id(self):
        a = perfil.ler(self.arq)
        p = perfil.salvar(self.arq, {"nick": "  Levi   Pereira ", "descricao": "x" * 300, "pais": "br"})
        self.assertEqual((p["nick"], p["pais"], p["id"]), ("Levi Pereira", "BR", a["id"]))
        self.assertEqual(len(p["descricao"]), perfil.DESC_MAX)

    def test_rejeita_nick_curto_e_pais_invalido(self):
        with self.assertRaises(ValueError):
            perfil.salvar(self.arq, {"nick": "ab"})
        with self.assertRaises(ValueError):
            perfil.salvar(self.arq, {"nick": "Levi", "pais": "BRA"})

    def test_personalizacao(self):
        p = perfil.salvar(self.arq, {"nick": "Levi", "titulo": "Estrategista", "moldura": "ouro", "cor": "sangue", "avatar": "lich_reanimador"})
        self.assertEqual((p["titulo"], p["moldura"], p["cor"], p["avatar"]), ("Estrategista", "ouro", "sangue", "lich_reanimador"))
        self.assertEqual(perfil.ler(self.arq)["moldura"], "ouro")
        for ruim in ({"moldura": "neon"}, {"cor": "x"}, {"titulo": "Rei"}, {"avatar": "../x"}):
            with self.assertRaises(ValueError):
                perfil.salvar(self.arq, {"nick": "Levi", **ruim})


if __name__ == "__main__":
    unittest.main()
