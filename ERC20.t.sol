// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {Test} from "forge-std/Test.sol";
import "src/ERC20.sol";

contract ERC20Test is Test {
    function testApprove() public {
        address spender = address(0x1234);
        uint256 amount = 1000;

        vm.startPrank(address(this));
        ERC20 erc20 = ERC20(address(this));
        assertTrue(erc20.approve(spender, amount));
        assertEq(erc20.allowance(address(this), spender), amount);
        vm.stopPrank();
    }

    function testTransferFrom() public {
        address sender = address(0x1234);
        address recipient = address(0x5678);
        uint256 amount = 100;

        vm.startPrank(sender);
        ERC20 erc20 = new ERC20("Test Token", "TST", 18);
        erc20.mint(sender, 1000);
        erc20.approve(address(this), amount);
        vm.stopPrank();

        vm.startPrank(recipient);
        bool success = erc20.transferFrom(sender, recipient, amount);
        assertTrue(success);
        assertEq(erc20.balanceOf(sender), 900);
        assertEq(erc20.balanceOf(recipient), amount);
        assertEq(erc20.allowance(sender, address(this)), 0);
        vm.stopPrank();
    }

    function testMint() public {
        ERC20 erc20 = new ERC20("Test Token", "TST", 18);
        address recipient = address(0x1234567890123456789012345678901234567890);
        uint256 amount = 1000;

        // Check initial state
        assertEq(erc20.totalSupply(), 0);
        assertEq(erc20.balanceOf(recipient), 0);

        // Mint tokens
        erc20.mint(recipient, amount);

        // Check updated state
        assertEq(erc20.totalSupply(), amount);
        assertEq(erc20.balanceOf(recipient), amount);
        assertEq(erc20.balanceOf(address(this)), 0);

        // Check event emission
        vm.expectEmit(true, true, false, true);
        emit ERC20.Transfer(address(0), recipient, amount);
        erc20.mint(recipient, amount);
    }

    function testBurn() public {
        // Set up initial state
        ERC20 token = new ERC20("Test Token", "TT", 18);
        token.mint(address(this), 1000);
        assertEq(token.balanceOf(address(this)), 1000);
        assertEq(token.totalSupply(), 1000);

        // Test burning tokens
        token.burn(address(this), 500);
        assertEq(token.balanceOf(address(this)), 500);
        assertEq(token.totalSupply(), 500);

        // Test that it reverts when burning more than the balance
        vm.expectRevert();
        token.burn(address(this), 501);
    }
}
