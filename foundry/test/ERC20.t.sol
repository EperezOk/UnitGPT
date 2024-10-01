// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {Test} from "forge-std/Test.sol";
import "src/ERC20.sol";

contract ERC20Test is Test {

    
    function testMint() public {
    ERC20 token = new ERC20("Test Token");
    address account = token.minter();
    uint256 amount = 100;
    token.mint(account, amount);
    require(token.balanceOf(account) == amount, "ERC20: mint failed");
}
    

}