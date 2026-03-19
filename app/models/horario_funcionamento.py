from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class HorarioFuncionamento(db.Model):
    __tablename__ = 'horarios_funcionamento'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dia_semana = db.Column(db.Integer, nullable=False) # 0-6 (Seg-Dom)
    abertura = db.Column(db.Time, nullable=False)
    fechamento = db.Column(db.Time, nullable=False)
    
    restaurante_id = db.Column(UUID(as_uuid=True), db.ForeignKey('restaurantes.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'dia_semana': self.dia_semana,
            'abertura': self.abertura.strftime('%H:%M'),
            'fechamento': self.fechamento.strftime('%H:%M')
        }
