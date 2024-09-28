// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {Test} from "forge-std/Test.sol";
import "src/ERC20.sol";

contract ERC20Test is Test {

    function test_mint() public {
        ERC20 token = new ERC20();
        address account = 0x123456789;
        uint256 amount = 100;

        // Initial balance
        assertEq(token.balanceOf(account), 0);

        // Mint tokens
        token.mint(account, amount);

        // Check balance after minting
        assertEq(token.balanceOf(account), amount);
    }
}