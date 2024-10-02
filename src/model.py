import os
import pprint as pp
from jinja2 import Template
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import subprocess

class Model:
    def __init__(self, docs, embedding_model = "mxbai-embed-large", test_model = ChatOllama(model="llama3.1:8b", temperature=0, top_p=1), compilation_model = ChatOllama(model="llama3.1:8b", temperature=0, top_p=1)):
        self.root = os.path.abspath(os.path.join(os.getcwd()))
        self.generated_tests = []
        self.embedding_model = OllamaEmbeddings(model=embedding_model)
        self.vectorstore = Chroma.from_documents(
            documents=docs,
            collection_name="foundry_tests",
            embedding=self.embedding_model,
            persist_directory=f"{self.root}/chroma_db"
        )
        self.test_model = test_model
        self.compilation_model = compilation_model

        self.PROMPT_TEMPLATE = """
        Based on the test function ([reference function test code]) which tests the function code example ([reference function code example]), generate a corresponding test function for the ([function to be tested]) function within the ([contract code to be tested]) contract. This function is for use within the Foundry framework for writing smart contracts.

        ---

        [reference function test code]: {reference_function_test_code}
        [reference function code example]: {reference_function_code_example}
        [contract code to be tested]: {contract_code}
        [function code to be tested]: {function_code}

        ---

        Your output MUST be a single valid Solidity function, with the setup and assertions necessary to test the function. Do NOT wrap the function in a markdown code block.
        REMEMBER, do NOT include a description of the function or any other text, only the code.
        REMEMBER, you MUST only generate a single function, not a full test contract.
        """

        self.ERROR_PROMPT_TEMPLATE = """
        I wrote the Solidity test function ([test function code]) to run on the Foundry framework. When this code is compiled with Foundry, I get this error ([compiler error]).
        This test is for the function ([function code to be tested]) within the contract ([contract code to be tested]). 

        Your task is to understand the test I provided, fix the test code, and correct the error within the test. You MUST modify the test function code while maintaining its functionality, but do NOT add other unrelated code.

        ---

        [test function code]: {test_function}
        [compiler error]: {error_info}
        [function code to be tested]: {function_code}
        [contract code to be tested]: {contract_code}

        ---

        Your output MUST be a single valid Solidity function, with the setup and assertions necessary to test the function. Do NOT wrap the function in a markdown code block.
        REMEMBER, do NOT include a description of the function or any other text, only the code.
        REMEMBER, you MUST only generate a single test function, not a full test contract.
        """

        self.reference_function_code_example = """
        function transfer(address to, uint256 amount) public virtual override returns (bool) {
            address owner = msg.sender;
            _transfer(owner, to, amount);
            return true;
        }
        """

        self.reference_function_test_code = """
        function test_transfer() public {
            ERC20 token = new ERC20("USD Coin", "USDC");
            address owner = address(this);
            address recipient = address(0x1);
            token.mint(owner, 100);

            token.transfer(recipient, 50);
            assertEq(token.balanceOf(owner), 50);
            assertEq(token.balanceOf(recipient), 50);
        }
        """

        self.function_code = """
        function mint(address account, uint256 amount) public virtual {
            require(account != address(0), "ERC20: mint to the zero address");

            _beforeTokenTransfer(address(0), account, amount);

            _totalSupply += amount;
            unchecked {
                // Overflow not possible: balance + amount is at most totalSupply + amount, which is checked above.
                _balances[account] += amount;
            }
            emit Transfer(address(0), account, amount);

            _afterTokenTransfer(address(0), account, amount);
        }
        """
    

    def generate_test_function(self, contract_path, contract_name, recompile_tries = False, verbose=True):
        if verbose:
            print("**************************************************")
            print("Generating Test Function Code")
            print("**************************************************")
        prompt = ChatPromptTemplate.from_template(self.PROMPT_TEMPLATE)

        chain = prompt | self.test_model | StrOutputParser()

        with open(contract_path, "r") as f:    
            contract_code = f.read()

        response = chain.invoke({
            "reference_function_test_code": self.reference_function_test_code,
            "reference_function_code_example": self.reference_function_code_example,
            "contract_code": contract_code,
            "function_code": self.function_code
        })

        if verbose:
            print("**************************************************")
            print("Test Function Code generated")
            print(response)
            print("**************************************************")

        if recompile_tries > 0:
            if verbose:
                print("**************************************************")
                print("Initiating Recompile Iteration")
                print("**************************************************")
            response = self.recompile_output(contract_path, contract_name, response, recompile_tries=recompile_tries)

        self.generated_tests.append(response)


    def generate_output(self, contract_name, output_path, verbose=True):
        return self._generate_output(contract_name, output_path, self.generated_tests, verbose=verbose)

    
    def _generate_output(self, contract_name, output_path, tests, verbose=False):
        if verbose:
            print("**************************************************")
            print(f"Generating output")
            print("**************************************************")
        template = """// SPDX-License-Identifier: MIT
        pragma solidity ^0.8.0;

        import {Test} from "forge-std/Test.sol";
        import "src/{{ contract_name }}.sol";

        contract {{ contract_name }}Test is Test {

            {% for test in tests %}
            {{ test }}
            {% endfor %}

        }
        """

        t = Template(template)

        test_file_content = t.render(
            contract_name=contract_name,
            tests = tests,
        )

        with open(f"{output_path}/{contract_name}.t.sol", "w") as file:
            file.write(test_file_content)

        if verbose:
            print("**************************************************")
            print(f"Contract generated in: {output_path}/{contract_name}.t.sol")
            print("**************************************************")


    def get_compile_errors(self, test_function, contract_name):
        output_path = f"{self.root}/foundry/test"
        self._generate_output(contract_name, output_path, [test_function], verbose=False)
        
        foundry_dir = os.path.join(self.root, "foundry")

        command = ["forge", "test", "--match-contract", contract_name]

        result = subprocess.run(command, cwd=foundry_dir, capture_output=True, text=True)

        if os.path.exists(f"{output_path}/{contract_name}.t.sol"):
            os.remove(f"{output_path}/{contract_name}.t.sol")

        return result.stdout


    def recompile_output(self, contract_path, contract_name, test_function, recompile_tries = 5, verbose = True):
        if recompile_tries == 0:
            if verbose:
                print("**************************************************")
                print("No more recompile tries, ending iteration.")
                print("**************************************************")
            return test_function
        if verbose:
            print("**************************************************")
            print("Recompiling function")
            print("**************************************************")

        compiler_errors = self.get_compile_errors(test_function, contract_name)
        if "Compiler run successful" in compiler_errors:
            if verbose:
                print("**************************************************")
                print("Compiler run successfully, ending iteration.")
                print("**************************************************")
            return test_function
        
        if verbose:
            print("**************************************************")
            print("Compiler run into errors.")
            print(compiler_errors)
            print("**************************************************")

        error_prompt = ChatPromptTemplate.from_template(self.ERROR_PROMPT_TEMPLATE)

        chain = error_prompt | self.compilation_model | StrOutputParser()

        with open(contract_path, "r") as f:    
            contract_code = f.read()

        error_response = chain.invoke({
            "error_info": compiler_errors,
            "test_function": test_function,
            "contract_code": contract_code,
            "function_code": self.function_code
        })

        if verbose:
            print("**************************************************")
            print("New response generated by recompiling errors")
            print(error_response)
            print("**************************************************")

        return self.recompile_output(contract_path, contract_name, error_response, recompile_tries - 1, verbose = verbose)