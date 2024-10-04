import re

class ContractParser:
    def __init__(self, contract_path) -> None:
        with open(contract_path, "r") as file:
            self.solidity_contract = file.read()

    @property
    def str_functions_with_names(self):
        start_idx = 0
        str_functions = []
        for line_num, line in enumerate(self.solidity_contract.splitlines(), start=1):
            if line.startswith("    function") or line.startswith("    receive"):
                start_idx = line_num
            if line.startswith("    }"):
                lines = self.solidity_contract.splitlines()[start_idx - 1:line_num]
                func_code = '\n'.join(lines)
                if func_code: str_functions.append(func_code)

        function_names = [self._extract_function_name(f) for f in str_functions]

        return str_functions, function_names

    def _extract_function_name(self, func_code):
            pattern = r'\s+(function)\s+(\w+)\s*'
            match = re.match(pattern, func_code)
            return match.group(2) if match else None