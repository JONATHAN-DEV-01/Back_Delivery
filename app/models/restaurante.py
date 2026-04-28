import uuid
import math
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db
from app.models.loja_categoria import loja_categorias


class Restaurante(db.Model):
    __tablename__ = 'restaurantes'

    id           = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_fantasia = db.Column(db.String(50), nullable=False)
    razao_social  = db.Column(db.String(255), nullable=False)
    cnpj          = db.Column(db.String(14), nullable=False, unique=True)
    logotipo      = db.Column(db.String(255), nullable=True)
    capa          = db.Column(db.String(255), nullable=True)
    descricao     = db.Column(db.String(500), nullable=True)
    categoria_id  = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=True)

    # Endereço detalhado
    endereco          = db.Column(db.String(254), nullable=False)
    logradouro        = db.Column(db.String(254), nullable=True)
    bairro            = db.Column(db.String(100), nullable=True)
    cidade            = db.Column(db.String(100), nullable=True)
    estado            = db.Column(db.String(2),   nullable=True)
    numero            = db.Column(db.String(10),  nullable=True)
    cep               = db.Column(db.String(10),  nullable=True)
    sem_numero        = db.Column(db.Boolean, default=False)
    complemento       = db.Column(db.String(100), nullable=True)
    ponto_referencia  = db.Column(db.String(100), nullable=True)
    telefone          = db.Column(db.String(11),  nullable=False)

    # Geolocalização (para filtragem geográfica RF-04 Req.7)
    latitude   = db.Column(db.Numeric(10, 7), nullable=True)
    longitude  = db.Column(db.Numeric(10, 7), nullable=True)

    # Status operacional
    ativo    = db.Column(db.Boolean, default=True, nullable=False)
    is_open  = db.Column(db.Boolean, default=False, nullable=False)  # RF-02 Req.6 / RF-06 Req.7

    # Metadados comerciais (RF-04 Req.6)
    nota_avaliacao        = db.Column(db.Numeric(3, 2), nullable=True)
    tempo_entrega_minutos = db.Column(db.Integer, nullable=True)
    valor_frete           = db.Column(db.Numeric(10, 2), nullable=True)
    pedido_minimo_centavos = db.Column(db.Integer, nullable=False, default=0)

    # Autenticação
    email = db.Column(db.String(254), nullable=False, unique=True)

    # Relacionamentos
    horarios    = db.relationship('HorarioFuncionamento', backref='restaurante', lazy=True, cascade='all, delete-orphan')
    produtos    = db.relationship('Produto', backref='restaurante', lazy=True, cascade='all, delete-orphan')
    otp_codes   = db.relationship('OTPCode', backref='restaurante', lazy=True, cascade='all, delete-orphan')

    # Relacionamento N:N com Categoria via loja_categorias (Req. 7.4)
    categorias = db.relationship('Categoria', secondary=loja_categorias, lazy=True)

    @property
    def is_open_agora(self):
        if not self.ativo:
            return False
            
        from datetime import datetime
        import pytz
        
        try:
            tz = pytz.timezone('America/Sao_Paulo')
            now = datetime.now(tz)
        except:
            now = datetime.utcnow()
            
        current_day = (now.weekday() + 1) % 7
        current_time = now.time()
        
        if not self.horarios:
            return True # Assumir aberto se não houver restrição configurada, mas for ativo
            
        for h in self.horarios:
            if h.dia_semana == current_day:
                if h.abertura <= current_time <= h.fechamento:
                    return True
        return False

    def distancia_km(self, user_lat: float, user_lon: float) -> float | None:
        """Calcula distância em km usando Haversine."""
        if self.latitude is None or self.longitude is None:
            return None
        R = 6371
        dlat = math.radians(float(self.latitude) - user_lat)
        dlon = math.radians(float(self.longitude) - user_lon)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(user_lat))
             * math.cos(math.radians(float(self.latitude)))
             * math.sin(dlon / 2) ** 2)
        return round(R * 2 * math.asin(math.sqrt(a)), 2)

    def to_dict(self):
        return {
            'id':                    str(self.id),
            'nome_fantasia':         self.nome_fantasia,
            'razao_social':          self.razao_social,
            'cnpj':                  self.cnpj,
            'logotipo':              self.logotipo,
            'capa':                  self.capa,
            'descricao':             self.descricao,
            'categoria':             self.categoria.nome if self.categoria else None,
            'categorias':            [{'id': c.id, 'nome': c.nome} for c in self.categorias],
            'endereco':              self.endereco,
            'logradouro':            self.logradouro,
            'bairro':                self.bairro,
            'cidade':                self.cidade,
            'estado':                self.estado,
            'numero':                self.numero,
            'cep':                   self.cep,
            'sem_numero':            self.sem_numero,
            'complemento':           self.complemento,
            'ponto_referencia':      self.ponto_referencia,
            'telefone':              self.telefone,
            'latitude':              float(self.latitude)  if self.latitude  else None,
            'longitude':             float(self.longitude) if self.longitude else None,
            'ativo':                 self.ativo,
            'is_open':               self.is_open_agora,
            'nota_avaliacao':        float(self.nota_avaliacao)        if self.nota_avaliacao        else None,
            'tempo_entrega_minutos': self.tempo_entrega_minutos,
            'valor_frete':           float(self.valor_frete)           if self.valor_frete           else None,
            'pedido_minimo_centavos': self.pedido_minimo_centavos,
            'email':                 self.email,
        }
