#! export $(cat .env | xargs)

docker-compose -f docker-compose-for-debug.yml down
docker volume rm polkascan-pre-harvester_sail-debug-mysql
docker-compose -f docker-compose-for-debug.yml up -d
sleep 10;

# load ENV variables.
export $(grep -v '^#' for-runfiles.private.env | xargs)

if [ -z $ENVIRONMENT ] || [ "$ENVIRONMENT" = "dev" ]; then
    ENVIRONMENT="dev"
fi

echo "==========================="
echo "Environment: $ENVIRONMENT"
echo "==========================="

if [ "$ENVIRONMENT" = "prod" ]; then
  echo "Wait for database..."
  # Let the DB start
  sleep 10;
fi

# Set path
export PYTHONPATH=$PYTHONPATH:$PWD:$PWD/../py-substrate-interface/:$PWD/py-scale-codec/

echo "Running migrations..."

# Run migrations
alembic upgrade head

echo "Ready go!"



