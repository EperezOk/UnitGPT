// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {Test} from "forge-std/Test.sol";
import "src/ERC20.sol";

contract ERC20Test is Test {

    
    function testMint(address account, uint256 amount) public {
    ERC20Token token = new ERC20Token();
    vm.startPrank(account);
    token.mint(account, amount);
    vm.stopPrank();

    assertEq(token.balanceOf(account), amount);
    assertEq(token.totalSupply(), amount);

    ERC20Token token2 = new ERC20Token();
    token2._balances[account] = 100;
    token2._totalSupply = 100;

    vm.startPrank(account);
    token2.mint(account, amount);
    vm.stopPrank();

    assertEq(token2.balanceOf(account), 100 + amount);
    assertEq(token2.totalSupply(), 100 + amount);
}
    

}