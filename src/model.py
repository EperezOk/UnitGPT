import os
from jinja2 import Template
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import subprocess
import json

from src.contract_parser import ContractParser

class Model:
    def __init__(self, docs, embedding_model = "mxbai-embed-large", test_model = ChatOllama(model="llama3.1:8b"), compilation_model = ChatOllama(model="llama3.1:8b"), description_model = ChatOllama(model="llama3.1:8b"), use_rag = True):
        self.root = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
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
        self.description_model = description_model
        self.use_rag = use_rag

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

        self.PROMPT_NO_RAG_TEMPLATE = """
        Generate a corresponding test function for the ([function to be tested]) function within the ([contract code to be tested]) contract. This function is for use within the Foundry framework for writing smart contracts.

        ---

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

        If the error is due to a non-existent variable, find feasible methods to reimplement it, or if it is not implementable, delete this line.

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

        self.DESCRIPTION_PROMPT = """
        Based on the following function written in the Solidity language, summarize its behavior in plain text, without giving a line-by-line description and without making any reference to the code.

        ```solidity
        {function_code}
        ```
        """
        

    def generate_function_description(self, public_function):
        prompt = ChatPromptTemplate.from_template(self.DESCRIPTION_PROMPT)

        chain = (
            prompt
            | self.description_model
            | StrOutputParser()
        )

        return chain.invoke({
            "function_code": public_function
        })
    
    def generate_test_function_no_rag(self, contract_code, function_code, recompile_tries, foundry_path, contract_name, verbose=True):
        prompt = ChatPromptTemplate.from_template(self.PROMPT_NO_RAG_TEMPLATE)
        chain = prompt | self.test_model | StrOutputParser()

        response = chain.invoke({
            "contract_code": contract_code,
            "function_code": function_code
        })

        if verbose:
            print("**************************************************")
            print("Function Code with no rag generated")
            print(response)
            print("**************************************************")

        if recompile_tries > 0:
            if verbose:
                print("**************************************************")
                print("Initiating Recompile Iteration")
                print("**************************************************")
            response = self.recompile_output(function_code, foundry_path, contract_code, contract_name, response, recompile_tries=recompile_tries)

        
        compiler_errors = self.get_compile_errors(foundry_path, response, contract_name)
        if "Compiler run successful" in compiler_errors or "compilation skipped" in compiler_errors:
            print("**************************************************")
            print("Adding generated tests")
            print("**************************************************")
            self.generated_tests.append(response)
        else:
            print("**************************************************")
            print("Could not add generated test")
            print(compiler_errors)
            print("**************************************************")
    

    def generate_test_function(self, contract_code, function_code, reference_document, recompile_tries, foundry_path, contract_name, subtests=2, verbose=True):
        prompt = ChatPromptTemplate.from_template(self.PROMPT_TEMPLATE)

        chain = prompt | self.test_model | StrOutputParser()

        print("**************************************************")
        print("Creating subtests")
        print(reference_document)
        print("**************************************************")
        for subtest in json.loads(reference_document.metadata['tests'])[:subtests]:
            reference_function_test_code = subtest
            reference_function_code_example = reference_document.metadata['function']


            response = chain.invoke({
                "reference_function_test_code": reference_function_test_code,
                "reference_function_code_example": reference_function_code_example,
                "contract_code": contract_code,
                "function_code": function_code
            })

            if verbose:
                print("**************************************************")
                print("Subtest Function Code generated")
                print(response)
                print("**************************************************")

            if recompile_tries > 0:
                if verbose:
                    print("**************************************************")
                    print("Initiating Recompile Iteration")
                    print("**************************************************")
                response = self.recompile_output(function_code, foundry_path, contract_code, contract_name, response, recompile_tries=recompile_tries)

            compiler_errors = self.get_compile_errors(foundry_path, response, contract_name)
            if "Compiler run successful" in compiler_errors or "compilation skipped" in compiler_errors:
                print("**************************************************")
                print("Adding generated tests")
                print("**************************************************")
                self.generated_tests.append(response)
            else:
                print("**************************************************")
                print("Could not add generated test")
                print(compiler_errors)
                print("**************************************************")


    def generate_test_functions(self, foundry_path, contract_name, recompile_tries = 2, k=2, subtests=2, verbose=True):
        if verbose:
            print("**************************************************")
            print("Generating Test Function Code")
            print("**************************************************")


        if verbose:
            print("**************************************************")
            print("Parsing public or external functions")
            print("**************************************************")

        contract_path = f"{foundry_path}/src/{contract_name}.sol"
        cp = ContractParser(contract_path=contract_path)
        functions, function_names = cp.str_functions_with_names

        public_functions = []
        public_function_names = []

        for i, func in enumerate(functions):
            if 'public' in func or 'external' in func:
                public_functions.append(func)
                public_function_names.append(function_names[i])


        with open(contract_path, "r") as f:    
            contract_code = f.read()
        
        if self.use_rag:
            if verbose:
                print("**************************************************")
                print("Generating test functions WITH rag")
                print("**************************************************")
                print("**************************************************")
                print("Generating public functions descriptions")
                print("**************************************************")

            public_function_descriptions = []
            for public_function in public_functions:
                function_description = self.generate_function_description(public_function)
                public_function_descriptions.append(function_description)

            print("**************************************************")
            print("Generating tests descriptions")
            print("**************************************************")
            print("**************************************************")
            for i, function_description in enumerate(public_function_descriptions):
                found_functions = set()
                similar_documents = self.vectorstore.similarity_search(function_description, k=k)

                filtered_similar_documents = []
                for document in similar_documents:
                    metadata = document.metadata
                    if metadata['function'] not in found_functions:
                        filtered_similar_documents.append(document)
                        found_functions.add(metadata['function'])

                print(f"Generating {len(filtered_similar_documents)} tests for {public_function_names[i]}")
                for similar_document in filtered_similar_documents:
                    self.generate_test_function(contract_code, public_functions[i], similar_document, recompile_tries, foundry_path, contract_name, subtests, verbose)
            print("**************************************************")
        else:
            if verbose:
                print("**************************************************")
                print("Generating test functions WITHOUT rag")
                print("**************************************************")
            for public_function in public_functions:
                self.generate_test_function_no_rag(contract_code, public_function, recompile_tries, foundry_path, contract_name, verbose)


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


    def get_compile_errors(self, foundry_path, test_function, contract_name):
        output_path = f"{foundry_path}/test"
        self._generate_output(contract_name, output_path, [test_function], verbose=False)

        command = ["forge", "test", "--match-contract", contract_name]

        result = subprocess.run(command, cwd=foundry_path, capture_output=True, text=True)

        if os.path.exists(f"{output_path}/{contract_name}.t.sol"):
            os.remove(f"{output_path}/{contract_name}.t.sol")

        return result.stdout


    def recompile_output(self, function_code, foundry_path, contract_code, contract_name, test_function, recompile_tries = 5, verbose = True):
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

        compiler_errors = self.get_compile_errors(foundry_path, test_function, contract_name)
        if "Compiler run successful" in compiler_errors or "compilation skipped" in compiler_errors:
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

        error_response = chain.invoke({
            "error_info": compiler_errors,
            "test_function": test_function,
            "contract_code": contract_code,
            "function_code": function_code
        })

        if verbose:
            print("**************************************************")
            print("New response generated by recompiling errors")
            print(error_response)
            print("**************************************************")

        return self.recompile_output(function_code, foundry_path, contract_code, contract_name, error_response, recompile_tries - 1, verbose = verbose)