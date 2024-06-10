
Before you run docker:

```
grep vm.max_map_count /etc/sysctl.conf
vm.max_map_count=262144
sysctl -w vm.max_map_count=262144
```

To permanently change the value for the vm.max_map_count setting, update the value in /etc/sysctl.conf.


# Minio

For some reason the minio setup is broken you will need to add the secret keys like this:
```
mc admin user svcacct add local root --access-key 499jdT1xhXqPof6R7CMn --secret-key Gq5CUufdtjy5nfvbtYdVvqbfqG2hE0CYN5pgXhy7
```

Other examples:

1. Add a new service account for user 'foobar' to MinIO server with a name and description.
$ mc admin user svcacct add myminio foobar --name uploaderKey --description "foobar uploader scripts"

2. Add a new service account to MinIO server with specified access key and secret key for user 'foobar'.
$ mc admin user svcacct add myminio foobar --access-key "myaccesskey" --secret-key "mysecretkey"

3. Add a new service account to MinIO server with specified access key and random secret key for user 'foobar'.
   $ mc admin user svcacct add myminio foobar --access-key "myaccesskey"

4. Add a new service account to MinIO server with specified secret key and random access key for user 'foobar'.
$ mc admin user svcacct add myminio foobar --secret-key "mysecretkey"

5. Add a new service account to MinIO server with specified expiry date in the future for user 'foobar'.
$ mc admin user svcacct add myminio foobar --expiry 2023-06-24T10:00:00-07:00

6. To get the aliast list:
mc alias list

