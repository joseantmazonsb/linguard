version_file="version.yaml"
version=$(poetry version -s)
commit=$(git rev-parse HEAD)
echo -e "!yamlable/version_info\nrelease: $version\ncommit: $commit" > "$version_file"