# Sensei CLI

## Installation

```
pip install sensei-cli
```

## Example Usage

Note: Run `sensei --help` for further info.

### List files

```bash
$ sensei --ls
(DIR) raw
(DIR) test1

2 results

$ sensei --ls raw
(DIR) raw/manual
raw/file1.txt
raw/file2.txt

3 results
```

### Recursively download everything into a directory called `sensei-data`

```bash
sensei --recursive --download /
# or more concise:
sensei -rd
```

### Recursively download everything into a directory called `/PATH/TO/MYDIR`

```bash
sensei --recursive --download / --out /PATH/TO/MYDIR
# or more concise:
sensei -rd / -o /PATH/TO/MYDIR
```

### Download specific file

```bash
sensei --download path/to/my_file.txt
# or more concise:
sensei -d path/to/my_file.txt
```

### Recursively download specific directory

```bash
sensei --recursive --download path/to/my_directory
# or more concise:
sensei -rd path/to/my_directory
```

### Download everything and overwrite existing files

```bash
sensei --recursive --overwrite --download /
# or more concise:
sensei -rwd
```

### Interactive mode

```bash
>> sensei -i
Entering interactive mode. Type 'help' for help, 'exit' to exit
sensei> ls
(DIR) dir1

1 results
sensei> ls dir1
(DIR) dir1/dir2

1 results
rdownload dir1/dir2
Recursively downloading from dir1/dir2 into /sensei-data...
```
