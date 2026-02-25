#!/bin/bash
set -e

echo "Aguardando Banco de Dados iniciar..."

# Opcional: Apenas por segurança, embora o depends_on com service_healthy já devesse resolver no compose
# Mas o entrypoint garante que as migrações rodem apenas quando o DB estiver 100%

echo "Executando migrações do banco de dados..."
flask db upgrade

echo "Iniciando a aplicação Flask..."
exec "$@"
