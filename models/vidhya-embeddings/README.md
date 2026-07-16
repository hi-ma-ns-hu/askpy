---
tags:
- sentence-transformers
- sentence-similarity
- feature-extraction
- generated_from_trainer
- dataset_size:8013
- loss:TripletLoss
base_model: sentence-transformers/all-MiniLM-L6-v2
widget:
- source_sentence: Find a file in python
  sentences:
  - "  os.walk  is the answer, this will find the first match:\n  import os\ndef find(name,\
    \ path):\n    for root, dirs, files in os.walk(path):\n        if name in files:\n\
    \            return os.path.join(root, name)\n And this will find all matches:\n\
    \  def find_all(name, path):\n    result = []\n    for root, dirs, files in os.walk(path):\n\
    \        if name in files:\n            result.append(os.path.join(root, name))\n\
    \    return result\n And this will match a pattern:\n  import os, fnmatch\ndef\
    \ find(pattern, path):\n    result = []\n    for root, dirs, files in os.walk(path):\n\
    \        for name in files:\n            if fnmatch.fnmatch(name, pattern):\n\
    \                result.append(os.path.join(root, name))\n    return result\n\
    find('*.txt', '/path/to/dir')"
  - " As for your first question: that code is perfectly fine and should work if \
    \ item  equals one of the elements inside  myList . Maybe you try to find a string\
    \ that does not  exactly  match one of the items or maybe you are using a float\
    \ value which suffers from inaccuracy.\n As for your second question: There's\
    \ actually several possible ways if \"finding\" things in lists.\n Checking if\
    \ something is inside\n This is the use case you describe: Checking whether something\
    \ is inside a list or not. As you know, you can use the  in  operator for that:\n\
    \  3 in [1, 2, 3] # => True\n Filtering a collection\n That is, finding all elements\
    \ in a sequence that meet a certain condition. You can use list comprehension\
    \ or generator expressions for that:\n  matches = [x for x in lst if fulfills_some_condition(x)]\n\
    matches = (x for x in lst if x > 6)\n The latter will return a  generator  which\
    \ you can imagine as a sort of lazy list that will only be built as soon as you\
    \ iterate through it. By the way, the first one is exactly equivalent to\n  matches\
    \ = filter(fulfills_some_condition, lst)\n in Python 2. Here you can see higher-order\
    \ functions at work. In Python 3,  filter  doesn't return a list, but a generator-like\
    \ object.\n Finding the first occurrence\n If you only want the first thing that\
    \ matches a condition (but you don't know what it is yet), it's fine to use a\
    \ for loop (possibly using the  else  clause as well, which is not really well-known).\
    \ You can also use\n  next(x for x in lst if ...)\n which will return the first\
    \ match or raise a  StopIteration  if none is found. Alternatively, you can use\n\
    \  next((x for x in lst if ...), [default value])\n Finding the location of an\
    \ item\n For lists, there's also the  index  method that can sometimes be useful\
    \ if you want to know  where  a certain element is in the list:\n  [1,2,3].index(2)\
    \ # => 1\n[1,2,3].index(4) # => ValueError\n However, note that if you have duplicates,\
    \  .index  always returns the lowest index:\n  [1,2,3,2].index(2) # => 1\n If\
    \ there are duplicates and you want all the indexes then you can use  enumerate()\
    \  instead:\n  [i for i,x in enumerate([1,2,3,2]) if x==2] # => [1, 3]"
  - " Based on github issue  #620 , it looks like you'll soon be able to do the following:\n\
    \  df[df['A'].str.contains(\"hello\")]\n Update:  vectorized string methods (i.e.,\
    \ Series.str)  are available in pandas 0.8.1 and up."
- source_sentence: is there a pythonic way to try something up to a maximum number
    of times?
  sentences:
  - " Personally:\n  for _ in range(50):\n    print \"Some thing\"\n if you don't\
    \ need  i . If you use Python  xrange  as there is no need to generate the whole\
    \ list beforehand."
  - " Building on Dana's answer, you might want to do this as a decorator:\n  def\
    \ retry(howmany):\n    def tryIt(func):\n        def f():\n            attempts\
    \ = 0\n            while attempts\n Then...\n  @retry(5)\ndef the_db_func():\n\
    \    # [...]\n Enhanced version that uses the  decorator  module\n  import decorator,\
    \ time\ndef retry(howmany, *exception_types, **kwargs):\n    timeout = kwargs.get('timeout',\
    \ 0.0) # seconds\n    @decorator.decorator\n    def tryIt(func, *fargs, **fkwargs):\n\
    \        for _ in xrange(howmany):\n            try: return func(*fargs, **fkwargs)\n\
    \            except exception_types or Exception:\n                if timeout\
    \ is not None: time.sleep(timeout)\n    return tryIt\n Then...\n  @retry(5, MySQLdb.Error,\
    \ timeout=0.5)\ndef the_db_func():\n    # [...]\n To install  the  decorator \
    \ module :\n  $ easy_install decorator"
  - "  The following link should solve all problems with Windows and SciPy ; just\
    \ choose the appropriate download. I was able to pip install the package with\
    \ no problems.  Every other solution I have tried gave me big headaches.\n Source:\
    \  http://www.lfd.uci.edu/~gohlke/pythonlibs/#scipy\nCommand: pip install [Local\
    \ File Location][Your specific file such as scipy-0.16.0-cp27-none-win_amd64.whl]\n\
    \  This assumes you have installed the following already:\n 1) Install Visual\
    \ Studio 2015/2013 with Python Tools\n(Is integrated into the setup options on\
    \ install of 2015)\n 2) Install Visual Studio C++ Compiler for Python\nSource:\
    \  http://www.microsoft.com/en-us/download/details.aspx?id=44266\nFile Name: VCForPython27.msi\n\
    \ 3) Install Python Version of choice\nSource: python.org\nFile Name (e.g.): python-2.7.10.amd64.msi"
- source_sentence: Does Python have an immutable list?
  sentences:
  - " If you are just looking for the files in a single directory (ie you are  not\
    \  trying to traverse a directory tree, which it doesn't look like), why not simply\
    \ use  os.listdir() :\n  import os\nfor fn in os.listdir('.'):\n     if os.path.isfile(fn):\n\
    \        print (fn)\n in place of  os.walk() . You can specify a directory path\
    \ as a parameter for  os.listdir() .  os.path.isfile()  will determine if the\
    \ given filename is for a file."
  - " Yes. It's called a  tuple .\n So, instead of  [1,2]  which is a  list  and which\
    \ can be mutated,  (1,2)  is a  tuple  and cannot.\n  Further Information:\n A\
    \ one-element  tuple  cannot be instantiated by writing  (1) , instead, you need\
    \ to write  (1,) . This is because the interpreter has various other uses for\
    \ parentheses.\n You can also do away with parentheses altogether:  1,2  is the\
    \ same as  (1,2)\n Note that a tuple is not  exactly  an immutable list. Click\
    \ here to read more about the  differences between lists and tuples"
  - " The standard Python list is not sorted in any form. The standard heapq module\
    \ can be used to append in O(log n) and remove the smallest one in O(log n), but\
    \ isn't a sorted list in your definition.\n There are various implementations\
    \ of balanced trees for Python that meet your requirements, e.g.  rbtree ,  RBTree\
    \ , or  pyavl ."
- source_sentence: Check whether a path is valid in Python without creating a file
    at the path's target
  sentences:
  - " If you're using Python 2.5 or later, the   uuid module   is already included\
    \ with the Python standard distribution.\n Ex:\n  >>> import uuid\n>>> uuid.uuid4()\n\
    UUID('5361a11b-615c-42bf-9bdb-e2c3790ada14')"
  - " If you have multiple versions of a package / module, you need to be using  virtualenv\
    \  (emphasis mine):\n    virtualenv  is a tool to create isolated Python environments.\n\
    \   The basic problem being addressed is one of dependencies and versions, and\
    \ indirectly permissions.  Imagine you have an application that needs version\
    \ 1 of LibFoo, but another application requires version 2. How can you use both\
    \ these applications?  If you install everything into  /usr/lib/python2.7/site-packages\
    \  (or whatever your platformâ\x80\x99s standard location is), itâ\x80\x99s easy\
    \ to end up in a situation where you unintentionally upgrade an application that\
    \ shouldnâ\x80\x99t be upgraded.\n   Or more generally, what if you want to install\
    \ an application and  leave it be ? If an application works, any change in its\
    \ libraries or the versions of those libraries can break the application.\n  \
    \ Also, what if you canâ\x80\x99t install packages into the global  site-packages\
    \  directory? For instance, on a shared host.\n   In all these cases,  virtualenv\
    \  can help you. It creates an environment that has its own installation directories,\
    \ that doesnâ\x80\x99t share libraries with other virtualenv environments (and\
    \ optionally doesnâ\x80\x99t access the globally installed libraries either).\n\
    \ That's why people consider  insert(0,  to be wrong -- it's an incomplete, stopgap\
    \ solution to the problem of managing multiple environments."
  - " tl;dr\n Call the  is_path_exists_or_creatable()  function defined below.\n Strictly\
    \ Python 3. That's just how we roll.\n A Tale of Two Questions\n The question\
    \ of \"How do I test pathname validity and, for valid pathnames, the existence\
    \ or writability of those paths?\" is clearly two separate questions. Both are\
    \ interesting, and neither have received a genuinely satisfactory answer here...\
    \ or, well,  anywhere  that I could grep.\n  vikki 's  answer  probably hews the\
    \ closest, but has the remarkable disadvantages of:\n Needlessly opening ( ...and\
    \ then failing to reliably close ) file handles.\n Needlessly writing ( ...and\
    \ then failing to reliable close or delete ) 0-byte files.\n Ignoring OS-specific\
    \ errors differentiating between non-ignorable invalid pathnames and ignorable\
    \ filesystem issues. Unsurprisingly, this is critical under Windows. ( See below.\
    \ )\n Ignoring race conditions resulting from external processes concurrently\
    \ (re)moving parent directories of the pathname to be tested. ( See below. )\n\
    \ Ignoring connection timeouts resulting from this pathname residing on stale,\
    \ slow, or otherwise temporarily inaccessible filesystems. This  could  expose\
    \ public-facing services to potential  DoS -driven attacks. ( See below. )\n We're\
    \ gonna fix all that.\n Question #0: What's Pathname Validity Again?\n Before\
    \ hurling our fragile meat suits into the python-riddled moshpits of pain, we\
    \ should probably define what we mean by \"pathname validity.\" What defines validity,\
    \ exactly?\n By \"pathname validity,\" we mean the  syntactic correctness  of\
    \ a pathname with respect to the  root filesystem  of the current system â\x80\
    \x93 regardless of whether that path or parent directories thereof physically\
    \ exist. A pathname is syntactically correct under this definition if it complies\
    \ with all syntactic requirements of the root filesystem.\n By \"root filesystem,\"\
    \ we mean:\n On POSIX-compatible systems, the filesystem mounted to the root directory\
    \ ( / ).\n On Windows, the filesystem mounted to  %HOMEDRIVE% , the colon-suffixed\
    \ drive letter containing the current Windows installation (typically but  not\
    \  necessarily  C: ).\n The meaning of \"syntactic correctness,\" in turn, depends\
    \ on the type of root filesystem. For  ext4  (and most but  not  all POSIX-compatible)\
    \ filesystems, a pathname is syntactically correct if and only if that pathname:\n\
    \ Contains no null bytes (i.e.,  \\x00  in Python).  This is a hard requirement\
    \ for all POSIX-compatible filesystems.\n Contains no path components longer than\
    \ 255 bytes (e.g.,  'a'*256  in Python). A path component is a longest substring\
    \ of a pathname containing no  /  character (e.g.,  bergtatt ,  ind ,  i , and\
    \  fjeldkamrene  in the pathname  /bergtatt/ind/i/fjeldkamrene ).\n Syntactic\
    \ correctness. Root filesystem. That's it.\n Question #1: How Now Shall We Do\
    \ Pathname Validity?\n Validating pathnames in Python is surprisingly non-intuitive.\
    \ I'm in firm agreement with  Fake Name  here: the official  os.path  package\
    \ should provide an out-of-the-box solution for this. For unknown (and probably\
    \ uncompelling) reasons, it doesn't. Fortunately, unrolling your own ad-hoc solution\
    \ isn't  that  gut-wrenching...\n  O.K., it actually is.  It's hairy; it's nasty;\
    \ it probably chortles as it burbles and giggles as it glows. But what you gonna\
    \ do?  Nuthin'.\n We'll soon descend into the radioactive abyss of low-level code.\
    \ But first, let's talk high-level shop. The standard  os.stat()  and  os.lstat()\
    \  functions raise the following exceptions when passed invalid pathnames:\n For\
    \ pathnames residing in non-existing directories, instances of  FileNotFoundError\
    \ .\n For pathnames residing in existing directories:\n Under Windows, instances\
    \ of  WindowsError  whose  winerror  attribute is  123  (i.e.,  ERROR_INVALID_NAME\
    \ ).\n Under all other OSes:\n For pathnames containing null bytes (i.e.,  '\\\
    x00' ), instances of  TypeError .\n For pathnames containing path components longer\
    \ than 255 bytes, instances of  OSError  whose  errcode  attribute is:\n Under\
    \ SunOS and the *BSD family of OSes,  errno.ERANGE . (This appears to be an OS-level\
    \ bug, otherwise referred to as \"selective interpretation\" of the POSIX standard.)\n\
    \ Under all other OSes,  errno.ENAMETOOLONG .\n Crucially, this implies that \
    \ only pathnames residing in existing directories are validatable.  The  os.stat()\
    \  and  os.lstat()  functions raise generic  FileNotFoundError  exceptions when\
    \ passed pathnames residing in non-existing directories, regardless of whether\
    \ those pathnames are invalid or not. Directory existence takes precedence over\
    \ pathname invalidity.\n Does this mean that pathnames residing in non-existing\
    \ directories are  not  validatable? Yes â\x80\x93 unless we modify those pathnames\
    \ to reside in existing directories. Is that even safely feasible, however? Shouldn't\
    \ modifying a pathname prevent us from validating the original pathname?\n To\
    \ answer this question, recall from above that syntactically correct pathnames\
    \ on the  ext4  filesystem contain no path components  (A)  containing null bytes\
    \ or  (B)  over 255 bytes in length. Hence, an  ext4  pathname is valid if and\
    \ only if all path components in that pathname are valid. This is true of  most\
    \   real-world filesystems  of interest.\n Does that pedantic insight actually\
    \ help us? Yes. It reduces the larger problem of validating the full pathname\
    \ in one fell swoop to the smaller problem of only validating all path components\
    \ in that pathname. Any arbitrary pathname is validatable (regardless of whether\
    \ that pathname resides in an existing directory or not) in a cross-platform manner\
    \ by following the following algorithm:\n Split that pathname into path components\
    \ (e.g., the pathname  /troldskog/faren/vild  into the list  ['', 'troldskog',\
    \ 'faren', 'vild'] ).\n For each such component:\n Join the pathname of a directory\
    \ guaranteed to exist with that component into a new temporary pathname (e.g.,\
    \  /troldskog ) .\n Pass that pathname to  os.stat()  or  os.lstat() . If that\
    \ pathname and hence that component is invalid, this call is guaranteed to raise\
    \ an exception exposing the type of invalidity rather than a generic  FileNotFoundError\
    \  exception. Why?  Because that pathname resides in an existing directory.  (Circular\
    \ logic is circular.)\n Is there a directory guaranteed to exist? Yes, but typically\
    \ only one: the topmost directory of the root filesystem (as defined above).\n\
    \ Passing pathnames residing in any other directory (and hence not guaranteed\
    \ to exist) to  os.stat()  or  os.lstat()  invites race conditions, even if that\
    \ directory was previously tested to exist. Why? Because external processes cannot\
    \ be prevented from concurrently removing that directory  after  that test has\
    \ been performed but  before  that pathname is passed to  os.stat()  or  os.lstat()\
    \ . Unleash the dogs of mind-fellating insanity!\n There exists a substantial\
    \ side benefit to the above approach as well:  security.  (Isn't  that  nice?)\
    \ Specifically:\n   Front-facing applications validating arbitrary pathnames from\
    \ untrusted sources by simply passing such pathnames to  os.stat()  or  os.lstat()\
    \  are susceptible to Denial of Service (DoS) attacks and other black-hat shenanigans.\
    \ Malicious users may attempt to repeatedly validate pathnames residing on filesystems\
    \ known to be stale or otherwise slow (e.g., NFS Samba shares); in that case,\
    \ blindly statting incoming pathnames is liable to either eventually fail with\
    \ connection timeouts or consume more time and resources than your feeble capacity\
    \ to withstand unemployment.\n The above approach obviates this by only validating\
    \ the path components of a pathname against the root directory of the root filesystem.\
    \ (If even  that's  stale, slow, or inaccessible, you've got larger problems than\
    \ pathname validation.)\n Lost?  Great.  Let's begin. (Python 3 assumed. See \"\
    What Is Fragile Hope for 300,  leycec ?\")\n  import errno, os\n# Sadly, Python\
    \ fails to provide the following magic number for us.\nERROR_INVALID_NAME = 123\n\
    '''\nWindows-specific error code indicating an invalid pathname.\nSee Also\n----------\n\
    https://msdn.microsoft.com/en-us/library/windows/desktop/ms681382%28v=vs.85%29.aspx\n\
    \    Official listing of all such codes.\n'''\ndef is_pathname_valid(pathname:\
    \ str) -> bool:\n    '''\n    `True` if the passed pathname is a valid pathname\
    \ for the current OS;\n    `False` otherwise.\n    '''\n    # If this pathname\
    \ is either not a string or is but is empty, this pathname\n    # is invalid.\n\
    \    try:\n        if not isinstance(pathname, str) or not pathname:\n       \
    \     return False\n        # Strip this pathname's Windows-specific drive specifier\
    \ (e.g., `C:\\`)\n        # if any. Since Windows prohibits path components from\
    \ containing `:`\n        # characters, failing to strip this `:`-suffixed prefix\
    \ would\n        # erroneously invalidate all valid absolute Windows pathnames.\n\
    \        _, pathname = os.path.splitdrive(pathname)\n        # Directory guaranteed\
    \ to exist. If the current OS is Windows, this is\n        # the drive to which\
    \ Windows was installed (e.g., the \"%HOMEDRIVE%\"\n        # environment variable);\
    \ else, the typical root directory.\n        root_dirname = os.environ.get('HOMEDRIVE',\
    \ 'C:') \\\n            if sys.platform == 'win32' else os.path.sep\n        assert\
    \ os.path.isdir(root_dirname)   # ...Murphy and her ironclad Law\n        # Append\
    \ a path separator to this directory if needed.\n        root_dirname = root_dirname.rstrip(os.path.sep)\
    \ + os.path.sep\n        # Test whether each path component split from this pathname\
    \ is valid or\n        # not, ignoring non-existent and non-readable path components.\n\
    \        for pathname_part in pathname.split(os.path.sep):\n            try:\n\
    \                os.lstat(root_dirname + pathname_part)\n            # If an OS-specific\
    \ exception is raised, its error code\n            # indicates whether this pathname\
    \ is valid or not. Unless this\n            # is the case, this exception implies\
    \ an ignorable kernel or\n            # filesystem complaint (e.g., path not found\
    \ or inaccessible).\n            #\n            # Only the following exceptions\
    \ indicate invalid pathnames:\n            #\n            # * Instances of the\
    \ Windows-specific \"WindowsError\" class\n            #   defining the \"winerror\"\
    \ attribute whose value is\n            #   \"ERROR_INVALID_NAME\". Under Windows,\
    \ \"winerror\" is more\n            #   fine-grained and hence useful than the\
    \ generic \"errno\"\n            #   attribute. When a too-long pathname is passed,\
    \ for example,\n            #   \"errno\" is \"ENOENT\" (i.e., no such file or\
    \ directory) rather\n            #   than \"ENAMETOOLONG\" (i.e., file name too\
    \ long).\n            # * Instances of the cross-platform \"OSError\" class defining\
    \ the\n            #   generic \"errno\" attribute whose value is either:\n  \
    \          #   * Under most POSIX-compatible OSes, \"ENAMETOOLONG\".\n       \
    \     #   * Under some edge-case OSes (e.g., SunOS, *BSD), \"ERANGE\".\n     \
    \       except OSError as exc:\n                if hasattr(exc, 'winerror'):\n\
    \                    if exc.winerror == ERROR_INVALID_NAME:\n                \
    \        return False\n                elif exc.errno in {errno.ENAMETOOLONG,\
    \ errno.ERANGE}:\n                    return False\n    # If a \"TypeError\" exception\
    \ was raised, it almost certainly has the\n    # error message \"embedded NUL\
    \ character\" indicating an invalid pathname.\n    except TypeError as exc:\n\
    \        return False\n    # If no exception was raised, all path components and\
    \ hence this\n    # pathname itself are valid. (Praise be to the curmudgeonly\
    \ python.)\n    else:\n        return True\n    # If any other exception was raised,\
    \ this is an unrelated fatal issue\n    # (e.g., a bug). Permit this exception\
    \ to unwind the call stack.\n    #\n    # Did we mention this should be shipped\
    \ with Python already?\n  Done.  Don't squint at that code. ( It bites. )\n Question\
    \ #2: Possibly Invalid Pathname Existence or Creatability, Eh?\n Testing the existence\
    \ or creatability of possibly invalid pathnames is, given the above solution,\
    \ mostly trivial. The little key here is to call the previously defined function\
    \  before  testing the passed path:\n  def is_path_creatable(pathname: str) ->\
    \ bool:\n    '''\n    `True` if the current user has sufficient permissions to\
    \ create the passed\n    pathname; `False` otherwise.\n    '''\n    # Parent directory\
    \ of the passed path. If empty, we substitute the current\n    # working directory\
    \ (CWD) instead.\n    dirname = os.path.dirname(pathname) or os.getcwd()\n   \
    \ return os.access(dirname, os.W_OK)\ndef is_path_exists_or_creatable(pathname:\
    \ str) -> bool:\n    '''\n    `True` if the passed pathname is a valid pathname\
    \ for the current OS _and_\n    either currently exists or is hypothetically creatable;\
    \ `False` otherwise.\n    This function is guaranteed to _never_ raise exceptions.\n\
    \    '''\n    try:\n        # To prevent \"os\" module calls from raising undesirable\
    \ exceptions on\n        # invalid pathnames, is_pathname_valid() is explicitly\
    \ called first.\n        return is_pathname_valid(pathname) and (\n          \
    \  os.path.exists(pathname) or is_path_creatable(pathname))\n    # Report failure\
    \ on non-fatal filesystem complaints (e.g., connection\n    # timeouts, permissions\
    \ issues) implying this path to be inaccessible. All\n    # other exceptions are\
    \ unrelated fatal issues and should not be caught here.\n    except OSError:\n\
    \        return False\n  Done  and  done.  Except not quite.\n Question #3: Possibly\
    \ Invalid Pathname Existence or Writability on Windows\n There exists a caveat.\
    \ Of course there does.\n As the official   os.access()  documentation  admits:\n\
    \    Note:  I/O operations may fail even when  os.access()  indicates that they\
    \ would succeed, particularly for operations on network filesystems which may\
    \ have permissions semantics beyond the usual POSIX permission-bit model.\n To\
    \ no one's surprise, Windows is the usual suspect here. Thanks to extensive use\
    \ of Access Control Lists (ACL) on NTFS filesystems, the simplistic POSIX permission-bit\
    \ model maps poorly to the underlying Windows reality. While this (arguably) isn't\
    \ Python's fault, it might nonetheless be of concern for Windows-compatible applications.\n\
    \ If this is you, a more robust alternative is wanted. If the passed path does\
    \  not  exist, we instead attempt to create a temporary file guaranteed to be\
    \ immediately deleted in the parent directory of that path â\x80\x93 a more portable\
    \ (if expensive) test of creatability:\n  import os, tempfile\ndef is_path_sibling_creatable(pathname:\
    \ str) -> bool:\n    '''\n    `True` if the current user has sufficient permissions\
    \ to create **siblings**\n    (i.e., arbitrary files in the parent directory)\
    \ of the passed pathname;\n    `False` otherwise.\n    '''\n    # Parent directory\
    \ of the passed path. If empty, we substitute the current\n    # working directory\
    \ (CWD) instead.\n    dirname = os.path.dirname(pathname) or os.getcwd()\n   \
    \ try:\n        # For safety, explicitly close and hence delete this temporary\
    \ file\n        # immediately after creating it in the passed path's parent directory.\n\
    \        with tempfile.TemporaryFile(dir=dirname): pass\n        return True\n\
    \    # While the exact type of exception raised by the above function depends\
    \ on\n    # the current version of the Python interpreter, all such types subclass\
    \ the\n    # following exception superclass.\n    except EnvironmentError:\n \
    \       return False\ndef is_path_exists_or_creatable_portable(pathname: str)\
    \ -> bool:\n    '''\n    `True` if the passed pathname is a valid pathname on\
    \ the current OS _and_\n    either currently exists or is hypothetically creatable\
    \ in a cross-platform\n    manner optimized for POSIX-unfriendly filesystems;\
    \ `False` otherwise.\n    This function is guaranteed to _never_ raise exceptions.\n\
    \    '''\n    try:\n        # To prevent \"os\" module calls from raising undesirable\
    \ exceptions on\n        # invalid pathnames, is_pathname_valid() is explicitly\
    \ called first.\n        return is_pathname_valid(pathname) and (\n          \
    \  os.path.exists(pathname) or is_path_sibling_creatable(pathname))\n    # Report\
    \ failure on non-fatal filesystem complaints (e.g., connection\n    # timeouts,\
    \ permissions issues) implying this path to be inaccessible. All\n    # other\
    \ exceptions are unrelated fatal issues and should not be caught here.\n    except\
    \ OSError:\n        return False\n Note, however, that even  this  may not be\
    \ enough.\n Thanks to User Access Control (UAC), the ever-inimicable Windows Vista\
    \ and all subsequent iterations thereof  blatantly lie  about permissions pertaining\
    \ to system directories. When non-Administrator users attempt to create files\
    \ in either the canonical  C:\\Windows  or  C:\\Windows\\system32  directories,\
    \ UAC superficially permits the user to do so while  actually  isolating all created\
    \ files into a \"Virtual Store\" in that user's profile. (Who could have possibly\
    \ imagined that deceiving users would have harmful long-term consequences?)\n\
    \ This is crazy. This is Windows.\n Prove It\n Dare we? It's time to test-drive\
    \ the above tests.\n Since NULL is the only character prohibited in pathnames\
    \ on UNIX-oriented filesystems, let's leverage that to demonstrate the cold, hard\
    \ truth â\x80\x93 ignoring non-ignorable Windows shenanigans, which frankly bore\
    \ and anger me in equal measure:\n  >>> print('\"foo.bar\" valid? ' + str(is_pathname_valid('foo.bar')))\n\
    \"foo.bar\" valid? True\n>>> print('Null byte valid? ' + str(is_pathname_valid('\\\
    x00')))\nNull byte valid? False\n>>> print('Long path valid? ' + str(is_pathname_valid('a'\
    \ * 256)))\nLong path valid? False\n>>> print('\"/dev\" exists or creatable? '\
    \ + str(is_path_exists_or_creatable('/dev')))\n\"/dev\" exists or creatable? True\n\
    >>> print('\"/dev/foo.bar\" exists or creatable? ' + str(is_path_exists_or_creatable('/dev/foo.bar')))\n\
    \"/dev/foo.bar\" exists or creatable? False\n>>> print('Null byte exists or creatable?\
    \ ' + str(is_path_exists_or_creatable('\\x00')))\nNull byte exists or creatable?\
    \ False\n Beyond sanity. Beyond pain. You will find Python portability concerns."
- source_sentence: Is there a generator version of `string.split()` in Python?
  sentences:
  - " My own  __init__.py  files are empty more often than not.  In particular, I\
    \ never have a  from blah import *  as part of  __init__.py  -- if \"importing\
    \ the package\" means getting all sort of classes, functions etc defined directly\
    \ as part of the package, then I would lexically copy the contents of  blah.py\
    \  into the package's  __init__.py  instead and remove  blah.py  (the multiplication\
    \ of source files does no good here).\n If you do insist on supporting the  import\
    \ *  idioms (eek), then using  __all__  (with as miniscule a list of names as\
    \ you can bring yourself to have in it) may help for damage control. In general,\
    \ namespaces and explicit imports are  good  things, and I strong suggest reconsidering\
    \ any approach based on systematically bypassing either or both concepts!-)"
  - " It is highly probable that   re.finditer  (link) uses fairly minimal memory\
    \ overhead.\n  def split_iter(string):\n    return (x.group(0) for x in re.finditer(r\"\
    [A-Za-z']+\", string))\n Demo:\n  >>> list( split_iter(\"A programmer's RegEx\
    \ test.\") )\n['A', \"programmer's\", 'RegEx', 'test']\n  edit:  I have just confirmed\
    \ that this takes constant memory in python 3.2.1, assuming my testing methodology\
    \ was correct. I created a string of very large size (1GB or so), then iterated\
    \ through the iterable with a  for  loop (NOT a list comprehension, which would\
    \ have generated extra memory). This did not result in a noticeable growth of\
    \ memory (that is, if there was a growth in memory, it was far far less than the\
    \ 1GB string)."
  - " Splits the string in  text  on delimiter:  \" \" .\n  words = text.split()\n\
    \ Split the string in  text  on delimiter:  \",\" .\n  words = text.split(\",\"\
    )\n The words variable will be a list datatype and contain a list of words from\
    \  text  split on the delimiter."
pipeline_tag: sentence-similarity
library_name: sentence-transformers
metrics:
- cosine_accuracy
model-index:
- name: SentenceTransformer based on sentence-transformers/all-MiniLM-L6-v2
  results:
  - task:
      type: triplet
      name: Triplet
    dataset:
      name: AskPy eval
      type: AskPy-eval
    metrics:
    - type: cosine_accuracy
      value: 0.8552188277244568
      name: Cosine Accuracy
---

# SentenceTransformer based on sentence-transformers/all-MiniLM-L6-v2

This is a [sentence-transformers](https://www.SBERT.net) model finetuned from [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). It maps sentences & paragraphs to a 384-dimensional dense vector space and can be used for retrieval.

## Model Details

### Model Description
- **Model Type:** Sentence Transformer
- **Base model:** [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) <!-- at revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41 -->
- **Maximum Sequence Length:** 256 tokens
- **Output Dimensionality:** 384 dimensions
- **Similarity Function:** Cosine Similarity
- **Supported Modality:** Text
<!-- - **Training Dataset:** Unknown -->
<!-- - **Language:** Unknown -->
<!-- - **License:** Unknown -->

### Model Sources

- **Documentation:** [Sentence Transformers Documentation](https://sbert.net)
- **Repository:** [Sentence Transformers on GitHub](https://github.com/huggingface/sentence-transformers)
- **Hugging Face:** [Sentence Transformers on Hugging Face](https://huggingface.co/models?library=sentence-transformers)

### Full Model Architecture

```
SentenceTransformer(
  (0): Transformer({'transformer_task': 'feature-extraction', 'modality_config': {'text': {'method': 'forward', 'method_output_name': 'last_hidden_state'}}, 'module_output_name': 'token_embeddings', 'architecture': 'BertModel'})
  (1): Pooling({'embedding_dimension': 384, 'pooling_mode': 'mean', 'include_prompt': True})
  (2): Normalize({})
)
```

## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```
Then you can load this model and run inference.
```python
from sentence_transformers import SentenceTransformer

# Download from the 🤗 Hub
model = SentenceTransformer("sentence_transformers_model_id")
# Run inference
sentences = [
    'Is there a generator version of `string.split()` in Python?',
    ' It is highly probable that   re.finditer  (link) uses fairly minimal memory overhead.\n  def split_iter(string):\n    return (x.group(0) for x in re.finditer(r"[A-Za-z\']+", string))\n Demo:\n  >>> list( split_iter("A programmer\'s RegEx test.") )\n[\'A\', "programmer\'s", \'RegEx\', \'test\']\n  edit:  I have just confirmed that this takes constant memory in python 3.2.1, assuming my testing methodology was correct. I created a string of very large size (1GB or so), then iterated through the iterable with a  for  loop (NOT a list comprehension, which would have generated extra memory). This did not result in a noticeable growth of memory (that is, if there was a growth in memory, it was far far less than the 1GB string).',
    ' Splits the string in  text  on delimiter:  " " .\n  words = text.split()\n Split the string in  text  on delimiter:  "," .\n  words = text.split(",")\n The words variable will be a list datatype and contain a list of words from  text  split on the delimiter.',
]
embeddings = model.encode(sentences)
print(embeddings.shape)
# [3, 384]

# Get the similarity scores for the embeddings
similarities = model.similarity(embeddings, embeddings)
print(similarities)
# tensor([[1.0000, 0.6789, 0.6939],
#         [0.6789, 1.0000, 0.6714],
#         [0.6939, 0.6714, 1.0000]])
```
<!--
### Direct Usage (Transformers)

<details><summary>Click to see the direct usage in Transformers</summary>

</details>
-->

<!--
### Downstream Usage (Sentence Transformers)

You can finetune this model on your own dataset.

<details><summary>Click to expand</summary>

</details>
-->

<!--
### Out-of-Scope Use

*List how the model may foreseeably be misused and address what users ought not to do with the model.*
-->

## Evaluation

### Metrics

#### Triplet

* Dataset: `AskPy-eval`
* Evaluated with [<code>TripletEvaluator</code>](https://sbert.net/docs/package_reference/sentence_transformer/evaluation.html#sentence_transformers.sentence_transformer.evaluation.TripletEvaluator)

| Metric              | Value      |
|:--------------------|:-----------|
| **cosine_accuracy** | **0.8552** |

<!--
## Bias, Risks and Limitations

*What are the known or foreseeable issues stemming from this model? You could also flag here known failure cases or weaknesses of the model.*
-->

<!--
### Recommendations

*What are recommendations with respect to the foreseeable issues? For example, filtering explicit content.*
-->

## Training Details

### Training Dataset

#### Unnamed Dataset

* Size: 8,013 training samples
* Columns: <code>sentence_0</code>, <code>sentence_1</code>, and <code>sentence_2</code>
* Approximate statistics based on the first 100 samples:
  |          | sentence_0                                                                        | sentence_1                                                                           | sentence_2                                                                           |
  |:---------|:----------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------|
  | type     | string                                                                            | string                                                                               | string                                                                               |
  | modality | text                                                                              | text                                                                                 | text                                                                                 |
  | details  | <ul><li>min: 5 tokens</li><li>mean: 13.51 tokens</li><li>max: 38 tokens</li></ul> | <ul><li>min: 40 tokens</li><li>mean: 179.61 tokens</li><li>max: 256 tokens</li></ul> | <ul><li>min: 47 tokens</li><li>mean: 170.66 tokens</li><li>max: 256 tokens</li></ul> |
* Samples:
  | sentence_0                                                              | sentence_1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | sentence_2                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
  |:------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | <code>Which is the recommended way to plot: matplotlib or pylab?</code> | <code> Official docs:  http://matplotlib.org/faq/usage_faq.html#matplotlib-pylab-and-pyplot-how-are-they-related<br> Both of those imports boil down do doing exactly the same thing and will run the exact same code, it is just different ways of importing the modules.<br> Also note that  matplotlib  has two interface layers, a state-machine layer managed by  pyplot  and the OO interface  pyplot  is built on top of, see  How can I attach a pyplot function to a figure instance?<br>  pylab  is a clean way to bulk import a whole slew of helpful functions (the  pyplot  state machine function, most of  numpy ) into a single name space.  The main reason this exists (to my understanding) is to work with  ipython  to make a very nice interactive shell which more-or-less replicates MATLAB (to make the transition easier and because it is good for playing around). See   pylab.py   and   matplotlib/pylab.py<br> At some level, this is  purely  a matter of taste and depends a bit on what you are doing.<br> If you are  not ...</code>                                                          | <code>  import matplotlib.pyplot as plt<br>import numpy as np<br>import matplotlib.mlab as mlab<br>import math<br>mu = 0<br>variance = 1<br>sigma = math.sqrt(variance)<br>x = np.linspace(-3, 3, 100)<br>plt.plot(x,mlab.normpdf(x, mu, sigma))<br>plt.show()</code>                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
  | <code>How to unquote a urlencoded unicode string in python?</code>      | <code> %uXXXX is a  non-standard encoding scheme  that has been rejected by the w3c, despite the fact that an implementation continues to live on in JavaScript land.<br> The more common technique seems to be to UTF-8 encode the string and then % escape the resulting bytes using %XX. This scheme is supported by urllib.unquote:<br>  >>> urllib2.unquote("%0a")<br>'\n'<br> Unfortunately, if you really  need  to support %uXXXX, you will probably have to roll your own decoder. Otherwise, it is likely to be far more preferable to simply UTF-8 encode your unicode and then % escape the resulting bytes.<br> A more complete example:<br>  >>> u"TanÄ±m"<br>u'Tan\u0131m'<br>>>> url = urllib.quote(u"TanÄ±m".encode('utf8'))<br>>>> urllib.unquote(url).decode('utf8')<br>u'Tan\u0131m'</code>                                                                                                                                                                                                                                                                                                                  | <code> Apparently  hashlib.sha1  isn't expecting a  unicode  object, but rather a sequence of bytes in a  str  object. Encoding your  unicode  string to a sequence of bytes (using, say, the UTF-8 encoding) should fix it:<br>  >>> import hashlib<br>>>> s = u'Ã©'<br>>>> hashlib.sha1(s.encode('utf-8'))<br> The error is because it is trying to convert the  unicode  object to a  str  automatically, using the default  ascii  encoding, which can't handle all those non-ASCII characters (since your string isn't pure ASCII).<br> A good starting point for learning more about Unicode and encodings is the  Python docs , and this  article by Joel Spolsky .</code>                                                                                                                                                                                                                                                                                                                                                                                                                     |
  | <code>Python 3 and static typing</code>                                 | <code> Thanks for reading my code!<br> Indeed, it's not hard to create a generic annotation enforcer in Python. Here's my take:<br>  '''Very simple enforcer of type annotations.<br>This toy super-decorator can decorate all functions in a given module that have<br>annotations so that the type of input and output is enforced; an AssertionError is<br>raised on mismatch.<br>This module also has a test function func() which should fail and logging facility<br>log which defaults to print.<br>Since this is a test module, I cut corners by only checking *keyword* arguments.<br>'''<br>import sys<br>log = print<br>def func(x:'int' = 0) -> 'str':<br>    '''An example function that fails type checking.'''<br>    return x<br># For simplicity, I only do keyword args.<br>def check_type(*args):<br>    param, value, assert_type = args<br>    log('Checking {0} = {1} of {2}.'.format(*args))<br>    if not isinstance(value, assert_type):<br>        raise AssertionError(<br>            'Check failed - parameter {0} = {1} not {2}.'<br>            .format(*args))<br>    return value<br>...</code> | <code> Yep, using the  staticmethod  decorator<br>  class MyClass(object):<br>    @staticmethod<br>    def the_static_method(x):<br>        print x<br>MyClass.the_static_method(2) # outputs 2<br> Note that some code might use the old method of defining a static method, using  staticmethod  as a function rather than a decorator. This should only be used if you have to support ancient versions of Python (2.2 and 2.3)<br>  class MyClass(object):<br>    def the_static_method(x):<br>        print x<br>    the_static_method = staticmethod(the_static_method)<br>MyClass.the_static_method(2) # outputs 2<br> This is entirely identical to the first example (using  @staticmethod ), just not using the nice decorator syntax<br> Finally, use   staticmethod()   sparingly! There are very few situations where static-methods are necessary in Python, and I've seen them used many times where a separate "top-level" function would have been clearer.<br>  The following is verbatim from the documentation: :<br>   A static method does not receive an implicit fi...</code> |
* Loss: [<code>TripletLoss</code>](https://sbert.net/docs/package_reference/sentence_transformer/losses.html#tripletloss) with these parameters:
  ```json
  {
      "distance_metric": "TripletDistanceMetric.EUCLIDEAN",
      "triplet_margin": 0.5
  }
  ```

### Training Hyperparameters
#### Non-Default Hyperparameters

- `per_device_train_batch_size`: 16
- `per_device_eval_batch_size`: 16
- `multi_dataset_batch_sampler`: round_robin

#### All Hyperparameters
<details><summary>Click to expand</summary>

- `overwrite_output_dir`: False
- `do_predict`: False
- `prediction_loss_only`: True
- `per_device_train_batch_size`: 16
- `per_device_eval_batch_size`: 16
- `per_gpu_train_batch_size`: None
- `per_gpu_eval_batch_size`: None
- `gradient_accumulation_steps`: 1
- `eval_accumulation_steps`: None
- `torch_empty_cache_steps`: None
- `learning_rate`: 5e-05
- `weight_decay`: 0.0
- `adam_beta1`: 0.9
- `adam_beta2`: 0.999
- `adam_epsilon`: 1e-08
- `max_grad_norm`: 1
- `num_train_epochs`: 3
- `max_steps`: -1
- `lr_scheduler_type`: linear
- `lr_scheduler_kwargs`: {}
- `warmup_ratio`: 0.0
- `warmup_steps`: 0
- `log_level`: passive
- `log_level_replica`: warning
- `log_on_each_node`: True
- `logging_nan_inf_filter`: True
- `save_safetensors`: True
- `save_on_each_node`: False
- `save_only_model`: False
- `restore_callback_states_from_checkpoint`: False
- `no_cuda`: False
- `use_cpu`: False
- `use_mps_device`: False
- `seed`: 42
- `data_seed`: None
- `jit_mode_eval`: False
- `use_ipex`: False
- `bf16`: False
- `fp16`: False
- `fp16_opt_level`: O1
- `half_precision_backend`: auto
- `bf16_full_eval`: False
- `fp16_full_eval`: False
- `tf32`: None
- `local_rank`: 0
- `ddp_backend`: None
- `tpu_num_cores`: None
- `tpu_metrics_debug`: False
- `debug`: []
- `dataloader_drop_last`: False
- `dataloader_num_workers`: 0
- `dataloader_prefetch_factor`: None
- `past_index`: -1
- `disable_tqdm`: False
- `remove_unused_columns`: True
- `label_names`: None
- `load_best_model_at_end`: False
- `ignore_data_skip`: False
- `fsdp`: []
- `fsdp_min_num_params`: 0
- `fsdp_config`: {'min_num_params': 0, 'xla': False, 'xla_fsdp_v2': False, 'xla_fsdp_grad_ckpt': False}
- `fsdp_transformer_layer_cls_to_wrap`: None
- `accelerator_config`: {'split_batches': False, 'dispatch_batches': None, 'even_batches': True, 'use_seedable_sampler': True, 'non_blocking': False, 'gradient_accumulation_kwargs': None}
- `deepspeed`: None
- `label_smoothing_factor`: 0.0
- `optim`: adamw_torch
- `optim_args`: None
- `adafactor`: False
- `group_by_length`: False
- `length_column_name`: length
- `ddp_find_unused_parameters`: None
- `ddp_bucket_cap_mb`: None
- `ddp_broadcast_buffers`: False
- `dataloader_pin_memory`: True
- `dataloader_persistent_workers`: False
- `skip_memory_metrics`: True
- `use_legacy_prediction_loop`: False
- `push_to_hub`: False
- `resume_from_checkpoint`: None
- `hub_model_id`: None
- `hub_strategy`: every_save
- `hub_private_repo`: None
- `hub_always_push`: False
- `gradient_checkpointing`: False
- `gradient_checkpointing_kwargs`: None
- `include_inputs_for_metrics`: False
- `include_for_metrics`: []
- `eval_do_concat_batches`: True
- `fp16_backend`: auto
- `push_to_hub_model_id`: None
- `push_to_hub_organization`: None
- `mp_parameters`: 
- `auto_find_batch_size`: False
- `full_determinism`: False
- `torchdynamo`: None
- `ray_scope`: last
- `ddp_timeout`: 1800
- `torch_compile`: False
- `torch_compile_backend`: None
- `torch_compile_mode`: None
- `include_tokens_per_second`: False
- `include_num_input_tokens_seen`: False
- `neftune_noise_alpha`: None
- `optim_target_modules`: None
- `batch_eval_metrics`: False
- `eval_on_start`: False
- `use_liger_kernel`: False
- `eval_use_gather_object`: False
- `average_tokens_across_devices`: False
- `prompts`: None
- `batch_sampler`: batch_sampler
- `multi_dataset_batch_sampler`: round_robin
- `router_mapping`: {}
- `learning_rate_mapping`: {}

</details>

### Training Logs
| Epoch  | Step | Training Loss | AskPy-eval_cosine_accuracy |
|:------:|:----:|:-------------:|:---------------------------:|
| 0.9980 | 500  | 0.2699        | -                           |
| 1.0    | 501  | -             | 0.8552                      |


### Training Time
- **Training**: 5.8 hours

### Framework Versions
- Python: 3.14.3
- Sentence Transformers: 5.6.0
- Transformers: 4.52.4
- PyTorch: 2.12.1
- Accelerate: 1.14.0
- Datasets: 5.0.0
- Tokenizers: 0.21.4

## Citation

### BibTeX

#### Sentence Transformers
```bibtex
@inproceedings{reimers-2019-sentence-bert,
    title = "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
    author = "Reimers, Nils and Gurevych, Iryna",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing",
    month = "11",
    year = "2019",
    publisher = "Association for Computational Linguistics",
    url = "https://arxiv.org/abs/1908.10084",
}
```

#### TripletLoss
```bibtex
@misc{hermans2017defense,
    title={In Defense of the Triplet Loss for Person Re-Identification},
    author={Alexander Hermans and Lucas Beyer and Bastian Leibe},
    year={2017},
    eprint={1703.07737},
    archivePrefix={arXiv},
    primaryClass={cs.CV}
}
```

<!--
## Glossary

*Clearly define terms in order to be accessible across audiences.*
-->

<!--
## Model Card Authors

*Lists the people who create the model card, providing recognition and accountability for the detailed work that goes into its construction.*
-->

<!--
## Model Card Contact

*Provides a way for people who have updates to the Model Card, suggestions, or questions, to contact the Model Card authors.*
-->