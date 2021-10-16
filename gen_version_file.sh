version_file="linguard/__version__.py"
version=$(poetry version -s)
commit=$(git rev-parse HEAD)
echo -e "release = '$version'\ncommit = '$commit'" > "$version_file"