#!/bin/bash
set -e

echo "Aguardando Banco de Dados iniciar e executando migrações..."

# Tenta rodar a migração em loop até o banco estar pronto
until flask db upgrade; do
  echo "Banco ainda indisponível ou migração falhou... tentando novamente em 2 segundos"
  sleep 2
done

echo "Banco de Dados está pronto e migrações aplicadas!"

echo "Iniciando a aplicação Flask..."
exec "$@"
