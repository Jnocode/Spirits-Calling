--[[
Spirits Calling — Nakama match module (scaffold)

Provides:
  * RPC "spirits_find_match": returns an open 1v1 match id (creates one if none).
  * Authoritative match handler "spirits_match": 2 players, team assignment,
    opcode relay. Game simulation stays on the UE listen server for now;
    this module is the foundation for matchmaking / server-authoritative play.

Loaded automatically from /nakama/data/modules by docker-compose.
]]

local nk = require("nakama")

-- ---------------------------------------------------------------- RPC

local function find_match(context, payload)
	local limit = 10
	local is_authoritative = true
	local label = "spirits_1v1"
	local min_size = 0
	local max_size = 1 -- matches with room for one more player

	local matches = nk.match_list(limit, is_authoritative, label, min_size, max_size)
	if #matches > 0 then
		return nk.json_encode({ match_id = matches[1].match_id })
	end

	local match_id = nk.match_create("spirits_match", { label = label })
	return nk.json_encode({ match_id = match_id })
end

nk.register_rpc(find_match, "spirits_find_match")

-- ---------------------------------------------------------------- Match handler

local M = {}

local OPCODE_TEAM_ASSIGN = 1
local OPCODE_STATE_RELAY = 2
local OPCODE_MATCH_END = 3

function M.match_init(context, setupstate)
	local state = {
		presences = {},
		next_team = 0,
		label = (setupstate and setupstate.label) or "spirits_1v1",
	}
	local tickrate = 5
	return state, tickrate, state.label
end

function M.match_join_attempt(context, dispatcher, tick, state, presence, metadata)
	local count = 0
	for _ in pairs(state.presences) do count = count + 1 end
	if count >= 2 then
		return state, false, "match full"
	end
	return state, true
end

function M.match_join(context, dispatcher, tick, state, presences)
	for _, presence in ipairs(presences) do
		state.presences[presence.session_id] = {
			presence = presence,
			team = state.next_team % 2,
		}
		local msg = nk.json_encode({
			user_id = presence.user_id,
			team = state.next_team % 2,
		})
		dispatcher.broadcast_message(OPCODE_TEAM_ASSIGN, msg, nil, nil)
		state.next_team = state.next_team + 1
	end
	return state
end

function M.match_leave(context, dispatcher, tick, state, presences)
	for _, presence in ipairs(presences) do
		state.presences[presence.session_id] = nil
	end
	return state
end

function M.match_loop(context, dispatcher, tick, state, messages)
	-- Relay gameplay messages to all other players.
	for _, message in ipairs(messages) do
		if message.op_code == OPCODE_STATE_RELAY or message.op_code == OPCODE_MATCH_END then
			dispatcher.broadcast_message(message.op_code, message.data, nil, message.sender)
		end
	end

	-- Close empty matches.
	local count = 0
	for _ in pairs(state.presences) do count = count + 1 end
	if count == 0 and tick > 50 then
		return nil
	end
	return state
end

function M.match_terminate(context, dispatcher, tick, state, grace_seconds)
	return state
end

function M.match_signal(context, dispatcher, tick, state, data)
	return state, data
end

return M
