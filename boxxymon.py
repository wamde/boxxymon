import codecs, grpc, os, string
import rpc_pb2 as ln, rpc_pb2_grpc as lnrpc

from os.path import expanduser

import curses
import time


LND_DIR = expanduser("~/.lnd")
macaroon = codecs.encode(open(LND_DIR + '/data/chain/bitcoin/mainnet/admin.macaroon', 'rb').read(), 'hex')
os.environ['GRPC_SSL_CIPHER_SUITES'] = 'HIGH+ECDSA'
cert = open(LND_DIR + '/tls.cert', 'rb').read()
ssl_creds = grpc.ssl_channel_credentials(cert)
channel_options = [
            ('grpc.max_message_length', 50 * 1024 * 1024),
            ('grpc.max_receive_message_length', 50 * 1024 * 1024)
        ]
channel = grpc.secure_channel('localhost:10009', ssl_creds, channel_options)


stub = lnrpc.LightningStub(channel)




def main():

	global channel_graph
	channel_graph = get_channel_graph()

	stdscr = curses.initscr()
	curses.noecho()
	curses.cbreak()

	try:
		while True:
			stdscr.addstr(0, 0, get_header_line())
			channel_line = 2
			for c in get_channels():
				stdscr.addstr(channel_line, 0, c.encode("UTF-8") + "    ")
				channel_line += 1
			stdscr.addstr(channel_line, 0, "-"*10 + " "*40)
			channel_line += 1
			for c in get_channels(active_only=False):
				stdscr.addstr(channel_line, 0, c.encode("UTF-8") + "    ")
				channel_line += 1
			stdscr.refresh()
			time.sleep(10)
	finally:
		curses.echo()
		curses.nocbreak()
		curses.endwin()
		for c in get_channels():
			print c


def get_header_line():

	# header
	response = stub.GetInfo(ln.GetInfoRequest(), metadata=[('macaroon', macaroon)])
	alias = response.alias
	chain = response.chains[0]
	version = response.version

	header = "%s (%s, lnd %s)" % (alias, chain, version)

	request = ln.ListChannelsRequest(
		active_only = True
		)
	response = stub.ListChannels(request, metadata=[('macaroon', macaroon)])
	active_channels = response.channels

	request = ln.ListChannelsRequest(
		inactive_only = True
		)
	response = stub.ListChannels(request, metadata=[('macaroon', macaroon)])
	inactive_channels = response.channels

	header += "\n"+("%d active channels and %d inactive channels" % (len(active_channels), len(inactive_channels)))
	return header

def get_channels(active_only=True):

	# channels
	if active_only:
		request = ln.ListChannelsRequest(
			active_only = True
			)
	else:
		request = ln.ListChannelsRequest(
			inactive_only = True
			)

	response = stub.ListChannels(request, metadata=[('macaroon', macaroon)])
	channels_ = response.channels

	channels = sorted(channels_, key=lambda c: int(c.chan_id), reverse=False)

	channel_number = 0
	channels_with_names = {}

	#print "%d active channels" % (len(channels))
	max_capacity = max([c.capacity for c in channels])
	for channel in channels:
		channels_with_names[string.ascii_uppercase[channel_number]] = {"channel": channel}
		capacity = channel.capacity
		local_balance = channel.local_balance
		chan_id = channel.chan_id
		remote_pubkey = channel.remote_pubkey
		node_alias = get_node_alias(channel_graph, remote_pubkey)
		if len(node_alias) >= 15:
			node_alias = node_alias[:13] + "/"
		else:
			node_alias += " "*(15-1-len(node_alias))
		score = channel_score(capacity, local_balance)
                channels_with_names[string.ascii_uppercase[channel_number]]["score"] = score
		yield (string.ascii_uppercase[channel_number] + "/ " + str(chan_id) + " "
			   + node_alias + " "
			   + channel_cursor(capacity, local_balance, max_capacity, score)
			   + " " + remote_pubkey)
		channel_number += 1

def channel_cursor(capacity, local_balance, max_capacity, score):
	max_capacity_digits = len("{:,}".format(max_capacity))
	num_steps = 60
	num_pluses = int(num_steps * float(local_balance) / float(capacity))
	cursor_string = "+"*num_pluses + "-"*(num_steps-num_pluses)
	balance_string = "(%d/%d sat)" % (local_balance, capacity)
	balance_string = "({local_balance:>{max_capacity_digits},} / {capacity:>{max_capacity_digits},}), score={score:.3f}".format(
		local_balance=local_balance, capacity=capacity,
		max_capacity_digits=max_capacity_digits,
		score=score
	)
	full_string = cursor_string + " " + balance_string
	return full_string

def channel_score(capacity, local_balance):
	fullness = float(local_balance) / float(capacity)
	return fullness  # there will be a better way but for now good enough

def get_channel_graph():
	request = ln.ChannelGraphRequest(
        include_unannounced=True,
    )
	response = stub.DescribeGraph(request, metadata=[('macaroon', macaroon)])
	return response

def get_node_alias(graph, pubkey):
	for p in graph.nodes:
		if p.pub_key == pubkey:
			return p.alias
	return ""

main()
