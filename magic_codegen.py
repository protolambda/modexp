from misc_crypto.utils.assembly import Contract
from misc_crypto.poseidon.contract import check_selector, to_32bytes


def code_gen_stack_magic():
    # VERY experimental, untested. Just a code-golf idea. By @protolambda
    # needs some work to utilize in solidity. DUP opcodes are great, but a problem to embed

    # TLDR from telegram:
    # - push n and x on stack to get started
    # - lots of DUPN operations, preparing a stack of 472 copies (within max stack size, I think), ordered exactly to repeatedly call mulmod on.
    #   Since there are only two cases: (xx x n) and (xx xx n), with trailing stack items that can be prepared.
    # - keep running mulmod until the stack is back to normal. Sometimes you need to dup the previous result (the xx xx n argument case)
    # - 472*3 (dup cost) + 362*8 (mulmod cost) = 5062 gas. Plus a little to put the result back in the function return data.

    # solidity assembly docs:
    # mulmod(x, y, m) 	  	F 	(x * y) % m with arbitrary precision arithmetic
    # yellow paper:
    # MULMOD = (s_0 * s_1) % s_2

    # case I: mulmod(xx, xx, n)
    # setup: n
    # *prev instructions*
    # pre: n xx
    #      dup1
    #  in: n xx xx
    #      mulmod
    # out: xx

    # case II: mulmod(xx, x, n)
    # setup: n x
    # *prev instructions*
    # pre: n x xx
    #  in: n x xx
    #      mulmod
    # out: xx

    contract = Contract()

    # TODO: create 'modexp' function
    check_selector(contract, "0xc4420fb4")  # poseidon(uint256[])

    contract.label("start")

    bits = bin(0xc19139cb84c680a6e14116da060561765e05aa45a1c72a34f082305b61f3f52)[2:]

    # load n
    contract.push('0x30644e72e131a029b85045b68181585d97816a916871ca8d3c208c16d87cfd47')

    # load x
    # The function has a single array param param
    # [Selector (4)] [Pointer (32)][Length (32)] [data1 (32)] ....
    contract.push(0x44 + (0x20 * 1)).calldataload()

    # stack filling preparation
    prev_stack_vars = ['n', 'x']

    # prepare stack first:
    for original_index, bit_value in reversed(list(enumerate(bits))):
        print(f"preparing bit: index: {original_index} value: {bit_value}")
        # prepare case I: push 'n' to the stack
        distance_n = list(reversed(prev_stack_vars)).index('n')
        if distance_n > 15:
            raise Exception("unlucky bit pattern, no 'n' within range to DUP. Need to mload, unhandled")
        # add 'n', by duplicating last 'n' value")
        contract.dup(distance_n+1)
        prev_stack_vars.append('n')

        if bit_value == "1":
            # prepare case II: push 'n' to the stack, then push 'x' to the stack
            distance_n = list(reversed(prev_stack_vars)).index('n')
            if distance_n > 15:
                raise Exception("unlucky bit pattern, no 'n' within range to DUP. Need to mload, unhandled")
            # add 'n', by duplicating last 'n' value")
            contract.dup(distance_n+1)
            prev_stack_vars.append('n')

            distance_x = list(reversed(prev_stack_vars)).index('x')
            if distance_x > 15:
                raise Exception("unlucky bit pattern, no 'x' within range to DUP. Need to mload, unhandled")
            # add 'x', by duplicating last 'x' value")
            contract.dup(distance_n+1)
            prev_stack_vars.append('x')

    print(f"prepared stack size: {len(prev_stack_vars)}")

    # done preparing stack, now write the mulmod and dup operations to interpret this all")
    # add initial xx value to the stack")
    contract.push(to_32bytes(1))

    # work through stack next:
    for i, v in enumerate(bits):
        print(f"bit {i}, value {v}")
        # stack is prepared, just need to run the calculations.
        #                    stack: ....... n xx
        contract.dup(1)    # stack: ....... n xx xx
        contract.mulmod()  # stack: ....... xx'
        if v == "1":
            #                    stack: ... n x xx'
            contract.mulmod()  # stack: ... xx''

    # stack: n x xx

    # done working through stack")
    # get stack back to normal, with result in stack 0")
    contract.swap(3)  # stack: xx x n

    contract.pop().pop()  # stack: xx
    contract.push(0)      # stack: xx 0
    contract.mstore()     # stack: (empty). Memory[0]: xx
    # Return 32 bytes from memory
    contract.push(0x20)
    contract.push(0x00)
    contract.return_()

    print(contract.create_tx_data())
    return contract


ABI = [
    {
        "constant": True,
        "inputs": [{"name": "input", "type": "uint256"}],
        "name": "modexp",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "pure",
        "type": "function",
    }
]

def build_contract():
    from web3 import Web3, EthereumTesterProvider
    from eth_utils import decode_hex

    contract = code_gen_stack_magic()

    w3 = Web3(EthereumTesterProvider())
    contract = w3.eth.contract(abi=ABI, bytecode=decode_hex(contract.create_tx_data()))
    tx_hash = contract.constructor().transact()
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
    instance = w3.eth.contract(address=tx_receipt.contractAddress, abi=ABI)

    assert instance.functions.modexp(3).call() == 4407920970296243842837207485651524041948558517760411303933


build_contract()