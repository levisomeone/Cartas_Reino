"""Jogo em rede local (LAN): descoberta de jogadores, convites e conexão da partida.

Cada computador roda o próprio servidor do jogo. Quem está com uma conta criada
anuncia sua presença por UDP (broadcast) e escuta os anúncios dos outros; a lista de
"jogadores na LAN" vem daí. Também dá para adicionar alguém digitando o endereço
(IP:porta), para redes onde o broadcast é bloqueado.

Desafio, passo a passo:
  1. A clica em "Desafiar" em B  -> A envia o convite para o servidor de B.
  2. B aceita escolhendo um deck  -> B envia o deck e o aceite para o servidor de A.
  3. O servidor de A cria a partida (A decide as regras, é o "anfitrião") e devolve
     o id e um token secreto; B passa a falar com a partida por A (via o próprio servidor
     de B, que repassa as requisições com o token).

Este módulo só cuida de rede e estado dos convites; criar a partida é com o servidor
(`criar_partida`, passada ao construtor).
"""

import ipaddress
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid

from . import perfil as perfil_mod

PORTA_UDP = 47800
PROTOCOLO = 1
TTL_PEER = 7.0            # segundos sem anúncio até sumir da lista
TTL_CONVITE = 60.0
INTERVALO = 2.0
MAX_CONVITES = 8

ID_RE = re.compile(r"[A-Za-z0-9_-]{3,24}")
CARTA_RE = re.compile(r"[a-z0-9_]{1,60}")


def ip_permitido(ip):
    """Só aceita endereços de rede local (privados, link-local e loopback)."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.is_private or a.is_loopback or a.is_link_local


def limpar_perfil(d):
    """Copia só os campos esperados de um perfil vindo da rede (nada vindo de fora é confiável)."""
    if not isinstance(d, dict):
        return None
    pid = str(d.get("id", ""))
    if not ID_RE.fullmatch(pid):
        return None
    pais = str(d.get("pais", "")).upper()
    carta = lambda k: (str(d.get(k, "")) if CARTA_RE.fullmatch(str(d.get(k, ""))) else "")  # noqa: E731
    return {
        "id": pid,
        "nick": " ".join(str(d.get("nick", "")).split())[:perfil_mod.NICK_MAX] or "Jogador",
        "pais": pais if re.fullmatch(r"[A-Z]{2}", pais) else "",
        "titulo": d.get("titulo") if d.get("titulo") in perfil_mod.TITULOS else "",
        "moldura": d.get("moldura") if d.get("moldura") in perfil_mod.MOLDURAS else "simples",
        "cor": d.get("cor") if d.get("cor") in perfil_mod.CORES else "ametista",
        "avatar": carta("avatar"),
    }


def ips_locais():
    achados = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))          # não envia nada: só descobre a interface de saída
        achados.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            achados.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in achados if not ip.startswith("127."))


def alvos_broadcast():
    alvos = {"255.255.255.255", "127.255.255.255"}
    for ip in ips_locais():
        p = ip.split(".")
        alvos.add(".".join(p[:3] + ["255"]))
    return sorted(alvos)


class ErroLan(Exception):
    """Erro que pode ser mostrado ao jogador."""


class Lan:
    def __init__(self, ler_perfil, porta_http, versao_cartas, criar_partida, udp=PORTA_UDP):
        self.ler_perfil = ler_perfil              # () -> perfil local (dict)
        self.porta_http = porta_http
        self.versao_cartas = versao_cartas
        self.criar_partida = criar_partida        # (deck_anfitriao, deck_convidado, perfil_a, perfil_c) -> {"id","token"}
        self.udp = udp
        self.lock = threading.RLock()
        self.peers = {}        # id -> {...perfil, ip, porta, visto, manual, estado, versao}
        self.recebidos = {}    # convite_id -> {...}
        self.enviado = None    # convite que eu mandei
        self.partida = None    # {"id", "ver", "oponente"} enquanto eu estiver numa partida em rede
        self.remotas = {}      # id local -> {"ip","porta","pid","token"}
        self._parar = threading.Event()
        self._threads = []

    # ------------------------------------------------------------------ presença
    def _meu_perfil(self):
        p = self.ler_perfil()
        return limpar_perfil(p) if p and p.get("criada") else None

    def presenca(self):
        """Dados públicos que qualquer um na rede pode ver sobre mim."""
        p = self._meu_perfil()
        if p is None:
            return None
        return dict(p, t="rn", v=PROTOCOLO, porta=self.porta_http, cartas=self.versao_cartas,
                    estado="em_partida" if self.partida else "livre")

    def iniciar(self):
        for alvo in (self._anunciar, self._escutar):
            t = threading.Thread(target=alvo, daemon=True)
            t.start()
            self._threads.append(t)

    def parar(self):
        self._parar.set()

    def _anunciar(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError:
            return
        ultimo_ping = 0.0
        while not self._parar.wait(INTERVALO):
            msg = self.presenca()
            if msg is not None:
                dados = json.dumps(msg).encode("utf-8")
                for alvo in alvos_broadcast():
                    try:
                        s.sendto(dados, (alvo, self.udp))
                    except OSError:
                        pass
            if time.time() - ultimo_ping > 4:           # confere quem foi adicionado por IP
                ultimo_ping = time.time()
                for p in [p for p in list(self.peers.values()) if p.get("manual")]:
                    try:
                        self._registrar(self._http(p["ip"], p["porta"], "GET", "/api/lan/quem"), p["ip"], manual=True)
                    except ErroLan:
                        pass
            self._limpar()

    def _escutar(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            s.bind(("", self.udp))
            s.settimeout(1.0)
        except OSError:
            return          # porta ocupada ou bloqueada: ainda dá para usar "adicionar por IP"
        while not self._parar.is_set():
            try:
                dados, (ip, _) = s.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not ip_permitido(ip):
                continue
            try:
                self._registrar(json.loads(dados.decode("utf-8")), ip)
            except (ValueError, UnicodeDecodeError):
                continue

    def _registrar(self, msg, ip, manual=False):
        if not isinstance(msg, dict) or msg.get("t") != "rn":
            return
        p = limpar_perfil(msg)
        meu = self.ler_perfil() or {}
        if p is None or p["id"] == meu.get("id"):
            return
        try:
            porta = int(msg.get("porta"))
        except (TypeError, ValueError):
            return
        if not 1024 <= porta <= 65535:
            return
        with self.lock:
            antigo = self.peers.get(p["id"], {})
            p.update(ip=ip, porta=porta, visto=time.time(), manual=manual or antigo.get("manual", False),
                     estado="em_partida" if msg.get("estado") == "em_partida" else "livre",
                     compativel=msg.get("cartas") == self.versao_cartas and msg.get("v") == PROTOCOLO)
            self.peers[p["id"]] = p

    def _limpar(self):
        agora = time.time()
        with self.lock:
            for pid in [k for k, p in self.peers.items() if agora - p["visto"] > (TTL_PEER * 2 if p.get("manual") else TTL_PEER)]:
                del self.peers[pid]
            for cid in [k for k, c in self.recebidos.items() if agora - c["criado"] > TTL_CONVITE]:
                del self.recebidos[cid]
            if self.enviado and self.enviado["status"] == "aguardando" and agora - self.enviado["criado"] > TTL_CONVITE:
                self.enviado["status"] = "expirou"

    # ------------------------------------------------------------------ HTTP entre servidores
    def _http(self, ip, porta, metodo, caminho, corpo=None, token=None, timeout=3.0):
        if not ip_permitido(ip):
            raise ErroLan("Endereço fora da rede local.")
        req = urllib.request.Request(f"http://{ip}:{porta}{caminho}", method=metodo,
                                     data=json.dumps(corpo).encode("utf-8") if corpo is not None else None)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("X-Token", token)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("erro")
            except (ValueError, OSError):
                msg = None
            raise ErroLan(msg or f"O outro computador recusou ({e.code}).") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise ErroLan("Não consegui falar com o outro computador.") from e

    def adicionar_por_ip(self, endereco):
        m = re.fullmatch(r"\s*([0-9.]{7,15})(?::(\d{2,5}))?\s*", str(endereco))
        if not m:
            raise ErroLan("Digite o endereço no formato 192.168.0.10 ou 192.168.0.10:8000.")
        ip, porta = m.group(1), int(m.group(2) or 8000)
        msg = self._http(ip, porta, "GET", "/api/lan/quem")
        if not isinstance(msg, dict) or msg.get("t") != "rn":
            raise ErroLan("Esse endereço não é um Cartas Reino com conta criada.")
        msg["porta"] = porta
        self._registrar(msg, ip, manual=True)
        return True

    # ------------------------------------------------------------------ convites: lado de quem convida
    def desafiar(self, peer_id, deck):
        eu = self._meu_perfil()
        if eu is None:
            raise ErroLan("Crie sua conta antes de jogar em rede.")
        with self.lock:
            if self.partida:
                raise ErroLan("Você já está numa partida.")
            peer = self.peers.get(peer_id)
            if peer is None:
                raise ErroLan("Esse jogador saiu da rede.")
            if peer["estado"] != "livre":
                raise ErroLan("Esse jogador está em partida.")
            if not peer["compativel"]:
                raise ErroLan("Esse jogador tem outra versão do jogo.")
            if self.enviado and self.enviado["status"] == "aguardando":
                raise ErroLan("Você já tem um desafio pendente.")
            convite = {"id": uuid.uuid4().hex[:12], "peer": peer_id, "nick": peer["nick"], "ip": peer["ip"],
                       "porta": peer["porta"], "deck": deck, "status": "aguardando", "criado": time.time()}
            self.enviado = convite
        try:
            self._http(peer["ip"], peer["porta"], "POST", "/api/lan/convite",
                       {"convite": convite["id"], "de": eu, "porta": self.porta_http})
        except ErroLan:
            with self.lock:
                self.enviado = None
            raise
        return convite

    def cancelar(self):
        with self.lock:
            c, self.enviado = self.enviado, None
        if c and c["status"] == "aguardando":
            try:
                self._http(c["ip"], c["porta"], "POST", "/api/lan/recusar", {"convite": c["id"], "cancelado": True}, timeout=2)
            except ErroLan:
                pass

    def convite_aceito(self, ip, corpo):
        """O outro lado aceitou: crio a partida aqui e devolvo o id e o token."""
        convidado = limpar_perfil(corpo.get("de"))
        with self.lock:
            c = self.enviado
            if (c is None or c["status"] != "aguardando" or c["id"] != corpo.get("convite")
                    or convidado is None or convidado["id"] != c["peer"] or ip != c["ip"]):
                raise ErroLan("Esse desafio não está mais valendo.")
            if self.partida:
                raise ErroLan("O anfitrião já está em outra partida.")
        eu = self._meu_perfil()
        info = self.criar_partida(c["deck"], corpo.get("deck"), eu, convidado)
        with self.lock:
            c["status"] = "aceito"
            self.partida = {"id": info["id"], "ver": 0, "oponente": convidado["nick"], "anfitriao": True}
        return info

    def convite_recusado(self, ip, corpo):
        with self.lock:
            c = self.enviado
            if c and c["id"] == corpo.get("convite") and c["ip"] == ip and c["status"] == "aguardando":
                c["status"] = "recusado"

    # ------------------------------------------------------------------ convites: lado de quem recebe
    def convite_recebido(self, ip, corpo):
        de = limpar_perfil(corpo.get("de"))
        try:
            porta = int(corpo.get("porta"))
        except (TypeError, ValueError):
            porta = 0
        cid = str(corpo.get("convite", ""))
        if de is None or not 1024 <= porta <= 65535 or not re.fullmatch(r"[0-9a-f]{12}", cid):
            raise ErroLan("Convite inválido.")
        if self._meu_perfil() is None:
            raise ErroLan("Esse jogador ainda não criou a conta.")
        with self.lock:
            if self.partida:
                raise ErroLan("Esse jogador está em partida.")
            if len(self.recebidos) >= MAX_CONVITES and cid not in self.recebidos:
                raise ErroLan("Esse jogador está com muitos convites.")
            for k in [k for k, v in self.recebidos.items() if v["de"]["id"] == de["id"]]:
                del self.recebidos[k]                  # um convite por pessoa
            self.recebidos[cid] = {"id": cid, "de": de, "ip": ip, "porta": porta, "criado": time.time()}

    def responder(self, convite_id, aceitar, deck_dict=None):
        with self.lock:
            c = self.recebidos.pop(convite_id, None)
        if c is None:
            raise ErroLan("Esse convite expirou.")
        eu = self._meu_perfil()
        if eu is None:
            raise ErroLan("Crie sua conta antes de jogar em rede.")
        if not aceitar:
            try:
                self._http(c["ip"], c["porta"], "POST", "/api/lan/recusar", {"convite": c["id"]}, timeout=2)
            except ErroLan:
                pass
            return None
        info = self._http(c["ip"], c["porta"], "POST", "/api/lan/aceitar",
                          {"convite": c["id"], "de": eu, "deck": deck_dict}, timeout=8)
        if not isinstance(info, dict) or not info.get("id") or not info.get("token"):
            raise ErroLan("O outro computador não conseguiu criar a partida.")
        rid = "r" + re.sub(r"\W", "", str(info["id"]))[:16]
        with self.lock:
            self.remotas[rid] = {"ip": c["ip"], "porta": c["porta"], "pid": str(info["id"]), "token": str(info["token"])}
            self.partida = {"id": rid, "ver": 1, "oponente": c["de"]["nick"], "anfitriao": False}
        return self.partida

    # ------------------------------------------------------------------ partida remota (lado do convidado)
    def repassar(self, rid, metodo, sufixo, corpo=None):
        """Repassa uma requisição da partida para o servidor do anfitrião."""
        with self.lock:
            r = self.remotas.get(rid)
        if r is None:
            raise ErroLan("Partida não encontrada.")
        caminho = f"/api/partidas/{r['pid']}{sufixo}"
        return self._http(r["ip"], r["porta"], metodo, caminho, corpo, token=r["token"], timeout=5)

    def sair_da_partida(self):
        with self.lock:
            p, self.partida, self.enviado = self.partida, None, None
            if p and p["id"] in self.remotas:
                del self.remotas[p["id"]]

    # ------------------------------------------------------------------ estado para a interface local
    def estado_ui(self):
        self._limpar()
        with self.lock:
            peers = sorted((dict(p) for p in self.peers.values()), key=lambda p: p["nick"].lower())
            for p in peers:
                p.pop("visto", None)
            env = dict(self.enviado) if self.enviado else None
            if env:
                env.pop("deck", None)
            return {
                "conta": self._meu_perfil() is not None, "ips": ips_locais(), "porta": self.porta_http,
                "peers": peers,
                "recebidos": [dict(c, ip=None) for c in self.recebidos.values()],
                "enviado": env, "partida": dict(self.partida) if self.partida else None,
            }
