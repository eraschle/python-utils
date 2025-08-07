((python-mode
  (eval . (unless (s-contains-p "/home/elyo/workspace/elyo/python-utils/.venv/bin/" (getenv "PATH"))
            (setenv "PATH" (concat "/home/elyo/workspace/elyo/python-utils/.venv/bin/" path-separator (getenv "PATH")))))
  (eval . (setenv "VIRTUALENV" "/home/elyo/workspace/elyo/python-utils/.venv/"))
  (eval . (setenv "PYTHONPATH"
                  (string-join
                   (seq-filter
                    (lambda (dir)
                      (not (string-blank-p dir)))
                    (seq-uniq
                     (append
                      (list
                       "/home/elyo/workspace/elyo/python-utils"
                       "/home/elyo/workspace/elyo/python-utils/analyzer/"
                       )
                      (when-let ((existing (getenv "PYTHONPATH")))
                        (string-split existing path-separator)))))
                   path-separator)))))
