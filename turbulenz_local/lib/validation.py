# Copyright (c) 2011,2013 Turbulenz Limited

class ValidationException(Exception):
    def __init__(self, issues):
        super(ValidationException, self).__init__()
        self.issues = issues

    def __str__(self):
        string = ''
        issues = self.issues
        first = True

        for issue in issues:
            if not first:
                string += '\n'

            issue_id = issue[0]
            errors = issue[1]['errors']
            warnings = issue[1]['warnings']

            string += 'For identifier %s:\n' % issue_id
            for e in errors:
                string += '    Error  : %s\n' % e
            for w in warnings:
                string += '    Warning: %s' % w

            first = False

        return string
