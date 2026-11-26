# bundles a kit tree that has examples/<game>/work scratch in it; prints size and whether work/ was packed
. "$(dirname "$0")/_common.sh"
mkdir -p kit/examples/demo/work/movie kit/tool/work
head -c 5000000 /dev/urandom > kit/examples/demo/work/movie/gameplay.avi
printf '#!/bin/sh\n' > kit/examples/demo/build.sh; printf 'k' > kit/tool/work/keep.txt
cp "$GST_ROOT/gst" kit/gst; echo 9.9.9 > kit/VERSION
python3 kit/gst bundle -o out
ls -l out/*.tar.gz | awk '{print "tarball bytes:", $5}'
tar tzf out/*.tar.gz | grep -E '/work/' | sed 's/^/packed: /'
