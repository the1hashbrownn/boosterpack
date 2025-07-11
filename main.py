import smartpy as sp

# All modern SmartPy code must be wrapped in a module.
@sp.module
def main():
    # ===================================================================
    # THE TRUE, FINAL FIX: All complex type definitions MUST be at the module level.
    # They cannot be defined inside a function or entrypoint.
    # ===================================================================
    t_tx_type: type = sp.record(
        to_ = sp.address, 
        token_id = sp.nat, 
        amount = sp.nat
    )
    
    t_transfer_params_type: type = sp.list[
        sp.record(from_ = sp.address, txs = sp.list[t_tx_type])
    ]

    class BoosterPack(sp.Contract):
        def __init__(self, admin, card_nft_contract):
            # Using self.data for initialization is correct.
            self.data.admin = admin
            self.data.card_nft_contract = card_nft_contract
            self.data.card_inventory = sp.cast(sp.big_map({}), sp.big_map[sp.nat, sp.nat])
            self.data.card_token_ids = sp.cast(set(), sp.set[sp.nat])
            self.data.random_seed = sp.bytes("0x00")

        @sp.entrypoint
        def deposit_card(self, params):
            # Using assert and Pythonic if/else is correct.
            assert sp.sender == self.data.admin, "NOT_ADMIN"
            if self.data.card_inventory.contains(params.token_id):
                self.data.card_inventory[params.token_id] += params.amount
            else:
                self.data.card_inventory[params.token_id] = params.amount
            self.data.card_token_ids.add(params.token_id)

        @sp.entrypoint
        def open_pack(self):
            assert sp.sender == sp.sender, "UNAUTHORIZED Placeholder"
            
            selected_cards = self._get_random_cards()

            txs = []
            for token_id in selected_cards:
                self.data.card_inventory[token_id] = sp.as_nat(self.data.card_inventory[token_id] - 1)
                txs.append(sp.record(to_=sp.sender, token_id=token_id, amount=1))
            
            transfer_payload = [sp.record(from_=sp.self_address, txs=txs)]
            
            # Use the predefined type from the module. Note the `main.` prefix is needed.
            contract_handle = sp.contract(
                main.t_transfer_params_type, 
                self.data.card_nft_contract, 
                "transfer"
            ).unwrap_some("INVALID_CARD_NFT_CONTRACT")
            
            sp.transfer(transfer_payload, sp.mutez(0), contract_handle)

        @sp.private
        def _get_random_cards(self):
            token_ids_list = self.data.card_token_ids.elements()
            assert sp.len(token_ids_list) >= 3, "NOT_ENOUGH_CARDS"
            entropy = sp.pack((sp.now, sp.sender, self.data.random_seed))
            selected = set()
            attempts = 0
            
            while sp.len(selected) < 3:
                hash = sp.sha256(entropy + sp.pack(attempts))
                # Using sp.nat() for slice arguments is correct, but no named parameters
                sliced_hash = sp.slice(hash, sp.nat(0), sp.nat(8)).unwrap_some(error="HASH_SLICE_ERROR")
                numeric_hash = sp.to_int(sliced_hash)
                target_index = sp.mod(sp.as_nat(numeric_hash), sp.len(token_ids_list))

                # Correctly iterating to find the element is required.
                current_index = 0
                candidate = sp.nat(0)
                for token_id in token_ids_list:
                    if current_index == target_index:
                        candidate = token_id
                    current_index += 1
                    
                if ~selected.contains(candidate) and self.data.card_inventory.get(candidate, 0) > 0:
                    selected.add(candidate)
                attempts += 1
                assert attempts < 100, "RANDOM_SELECTION_FAILED"

            self.data.random_seed = hash
            return selected.elements()

# The test block, which is now fully compliant.
@sp.add_test()
def test():
    # Must import the module.
    import main

    sp.h1("Booster Pack Contract Test")
    
    admin = sp.test_account("Admin")
    user1 = sp.test_account("User1")
    card_nft_account = sp.test_account("CardNFTContract")

    contract = sp.deploy(main.BoosterPack(
        admin = admin.address,
        card_nft_contract = card_nft_account.address
    ))
    
    sp.h2("Admin deposits cards")
    contract.deposit_card(token_id=1, amount=5, _sender=admin)
    contract.deposit_card(token_id=2, amount=5, _sender=admin)
    contract.deposit_card(token_id=3, amount=5, _sender=admin)
    contract.deposit_card(token_id=4, amount=5, _sender=admin)
    contract.deposit_card(token_id=5, amount=5, _sender=admin)
    
    sp.h2("User opens a pack")
    contract.open_pack(_sender=user1, _now=sp.timestamp(12345678))

    sp.verify(sp.len(contract.data.card_token_ids) == 5)